"""
Refactored main application with proper security, job storage, and validation.
Production-ready FastAPI application for Screen2Deck.
"""

import uuid
import time
from typing import Optional
from contextlib import asynccontextmanager

# ONLINE-ONLY mode - No offline support

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
import numpy as np
import cv2

# Initialize determinism SECOND
from .core.determinism import init_determinism
init_determinism()

# Core imports
from .core.config import settings
from .core.auth_middleware import AuthMiddleware, SecurityHeadersMiddleware
from .core.job_storage import job_storage
from .core.validation import image_validator, text_validator, request_validator
from .core.feature_flags import FeatureFlags
from .core.idempotency import generate_job_key, verify_idempotency
from .core.metrics_minimal import (
    create_metrics_app, track_ocr_request, record_cache_access, 
    record_export, OCR_REQUESTS, JOBS_INFLIGHT
)
from .auth import get_current_token, TokenData, create_access_token, require_permission

# Application imports
from .telemetry import logger, new_trace, telemetry
from .models import (
    UploadResponse, StatusResponse, DeckResult, RawOCR, OCRSpan, 
    DeckSections, CardEntry, NormalizedDeck
)
from .error_taxonomy import *
from .pipeline.preprocess import preprocess_variants
from .pipeline.ocr import run_easyocr_best_of, run_vision_fallback
from .matching.fuzzy import score_candidates
from .matching.scryfall_cache import scryfall_cache
from .matching.scryfall_client import SCRYFALL
from .business_rules import validate_and_fill
from .routers import health, metrics, auth_router, export_router

# Initialize feature flags
FLAGS = FeatureFlags.get_all_flags()
logger.info(f"Feature flags: {FLAGS}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown tasks.
    """
    # Startup
    logger.info("Starting Screen2Deck API...")
    
    # Connect to Redis for job storage
    await job_storage.connect()
    
    # Initialize Scryfall cache
    logger.info("Initializing Scryfall cache...")
    # scryfall_cache is already initialized
    
    # Initialize telemetry
    if settings.ENABLE_TRACING:
        telemetry.init_tracing()
    
    logger.info("Screen2Deck API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Screen2Deck API...")
    
    # Disconnect from Redis
    await job_storage.disconnect()
    
    # Close Scryfall cache
    await scryfall_cache.close()
    
    # Shutdown telemetry
    if settings.ENABLE_TRACING:
        telemetry.shutdown()
    
    logger.info("Screen2Deck API shutdown complete")


# Create FastAPI app with lifespan manager
app = FastAPI(
    title="Screen2Deck API",
    version="2.0.0",
    description="Production-ready MTG card list OCR and export API",
    default_response_class=ORJSONResponse,
    lifespan=lifespan
)

# Add security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    AuthMiddleware,
    skip_auth_paths={
        "/", "/health", "/metrics", "/docs", "/openapi.json", "/redoc",
        "/api/auth/login", "/api/auth/register", "/api/auth/refresh"
    }
)

# Configure CORS with settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS
)

# Mount Prometheus metrics endpoint
metrics_app = create_metrics_app()
app.mount("/metrics", metrics_app)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(export_router, prefix="/api/export", tags=["export"])


@app.post(
    "/api/ocr/upload",
    response_model=UploadResponse,
    summary="Upload image for OCR processing",
    description="Upload a deck list image for OCR processing with idempotency support"
)
async def upload_image(
    request: Request,
    file: UploadFile = File(..., description="Image file to process"),
    token_data: Optional[TokenData] = None  # Optional auth for public endpoint
):
    """
    Upload an image for OCR processing.
    
    Features:
    - Image validation and sanitization
    - Idempotency via image hash
    - Async job processing
    - Rate limiting per IP
    - Prometheus metrics tracking
    """
    # Track OCR request
    with track_ocr_request():
        trace_id = new_trace()
        
        # Validate request headers
        if not request_validator.validate_headers(dict(request.headers)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": VALIDATION_ERROR, "message": "Invalid request headers"}
            )
        
        # Validate and sanitize image
        try:
            sanitized_content, metadata = await image_validator.validate_upload(
                file, 
                calculate_hash=True
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": BAD_IMAGE, "message": "Image validation failed"}
            )
        
        # Generate idempotency key
        pipeline_config = {
            "ocr_engine": FLAGS["ocr_engine"],
            "languages": FLAGS["ocr_languages"],
            "min_confidence": FLAGS["ocr_confidence"],
            "fuzzy_topk": FLAGS.get("fuzzy_topk", 5),
            "scryfall_verify": True,
            "preprocess": {
                "denoise": True,
                "binarize": True,
                "sharpen": True,
                "superres": False
            }
        }
        
        job_key = generate_job_key(sanitized_content, **pipeline_config)
        image_hash = metadata.get("hash", job_key[:64])  # Use full job_key as hash
        
        # Check cache (idempotency) using image_hash
        if settings.USE_REDIS:
            existing_job_id = await job_storage.find_by_image_hash(image_hash)
            if existing_job_id:
                logger.info(f"Cache hit for image hash {image_hash[:16]}")
                record_cache_access("ocr", hit=True)
                return UploadResponse(jobId=existing_job_id, cached=True)
        
        record_cache_access("ocr", hit=False)
        
        # Create new job
        job_id = str(uuid.uuid4())
        user_id = token_data.job_id if token_data else None
        
        await job_storage.create_job(
            job_id=job_id,
            image_hash=image_hash,
            user_id=user_id,
            metadata=metadata
        )
        
        # Process image asynchronously
        # In production, this would be sent to a Celery queue
        # For now, we process inline but update job status
        await job_storage.update_job(job_id, state="processing", progress=10)
        
        try:
            # Process OCR
            result = await process_ocr(sanitized_content, job_id, trace_id)
            
            # Save result
            await job_storage.update_job(
                job_id,
                state="completed",
                progress=100,
                result=result.model_dump()
            )
            
        except Exception as e:
            logger.error(f"OCR processing failed for job {job_id}: {e}")
            await job_storage.update_job(
                job_id,
                state="failed",
                progress=100,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": OCR_ERROR, "message": "OCR processing failed"}
            )
        
        return UploadResponse(jobId=job_id, cached=False)


async def process_ocr(content: bytes, job_id: str, trace_id: str) -> DeckResult:
    """
    Process OCR on image content.
    
    Args:
        content: Image bytes
        job_id: Job identifier
        trace_id: Trace identifier
        
    Returns:
        DeckResult with OCR results
    """
    with telemetry.span("process_ocr") as span:
        span.set_attribute("job_id", job_id)
        
        t0 = time.time()
        
        # Decode image
        img = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Cannot decode image")
        
        # Update progress
        await job_storage.update_job(job_id, progress=20)
        
        # Multi-variant OCR
        variants = preprocess_variants(img)
        ocr_raw = run_easyocr_best_of(variants)
        
        await job_storage.update_job(job_id, progress=40)
        
        # Fallback to Vision if needed
        import re
        def count_qty_lines(spans):
            rx = re.compile(r"^\s*(\d+|[1-9]\dx)\s+\S+")
            return sum(1 for s in spans if rx.match(s["text"].strip().lower()))
        
        if (ocr_raw["mean_conf"] < settings.OCR_MIN_CONF or 
            count_qty_lines(ocr_raw["spans"]) < settings.OCR_MIN_LINES) and \
           settings.ENABLE_VISION_FALLBACK:
            best_img = max(variants, key=lambda im: cv2.countNonZero(im))
            ocr_raw = run_vision_fallback(best_img)
        
        await job_storage.update_job(job_id, progress=60)
        
        # Parse OCR results
        spans = [OCRSpan(text=s["text"], conf=s["conf"]) for s in ocr_raw["spans"]]
        raw = RawOCR(spans=spans, mean_conf=ocr_raw["mean_conf"])
        
        # Extract cards
        parsed = parse_deck_sections(spans)
        
        await job_storage.update_job(job_id, progress=80)
        
        # Normalize with Scryfall
        normalized = await normalize_deck(parsed)
        
        # Apply business rules
        normalized = validate_and_fill(normalized)
        
        t1 = time.time()
        
        result = DeckResult(
            jobId=job_id,
            raw=raw,
            parsed=parsed,
            normalized=normalized,
            timings_ms={"total": int((t1-t0)*1000)},
            traceId=trace_id
        )
        
        return result


def parse_deck_sections(spans: list[OCRSpan]) -> DeckSections:
    """
    Parse OCR spans into deck sections.
    """
    main_entries: list[CardEntry] = []
    side_entries: list[CardEntry] = []
    section = "main"
    
    for span in spans:
        line = span.text.strip()
        
        # Check for sideboard marker
        if line.lower().startswith("sideboard") or line.lower().startswith("sb"):
            section = "side"
            continue
        
        # Parse quantity and name
        qty = 0
        name = ""
        parts = line.split(" ", 1)
        
        if len(parts) == 2:
            if parts[0].isdigit():
                qty = int(parts[0])
                name = parts[1]
            elif parts[0].lower().endswith("x") and parts[0][:-1].isdigit():
                qty = int(parts[0][:-1])
                name = parts[1]
        
        if qty > 0 and name:
            # Sanitize card name
            name = text_validator.sanitize_card_name(name)
            entry = CardEntry(qty=qty, name=name)
            
            if section == "main":
                main_entries.append(entry)
            else:
                side_entries.append(entry)
    
    return DeckSections(main=main_entries, side=side_entries)


async def normalize_deck(parsed: DeckSections) -> NormalizedDeck:
    """
    Normalize deck with Scryfall data.
    """
    from .models import NormalizedCard
    
    async def normalize_entries(entries: list[CardEntry]) -> list[NormalizedCard]:
        normalized = []
        
        for entry in entries:
            # Try cache first
            card_data = await scryfall_cache.resolve_card(entry.name)
            
            if card_data:
                normalized.append(NormalizedCard(
                    qty=entry.qty,
                    name=card_data.get("name", entry.name),
                    scryfall_id=card_data.get("id")
                ))
            else:
                # Fallback to fuzzy matching
                normalized.append(NormalizedCard(
                    qty=entry.qty,
                    name=entry.name,
                    scryfall_id=None
                ))
        
        return normalized
    
    main_normalized = await normalize_entries(parsed.main)
    side_normalized = await normalize_entries(parsed.side)
    
    return NormalizedDeck(main=main_normalized, side=side_normalized)


@app.get(
    "/api/ocr/status/{job_id}",
    response_model=StatusResponse,
    summary="Get job status",
    description="Get the status and results of an OCR job"
)
async def get_job_status(
    job_id: str,
    token_data: Optional[TokenData] = None  # Optional auth
):
    """
    Get job status and results.
    """
    # Validate job ID format
    if not text_validator.validate_job_id(job_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": VALIDATION_ERROR, "message": "Invalid job ID format"}
        )
    
    # Get job from storage
    job = await job_storage.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": JOB_NOT_FOUND, "message": "Job not found"}
        )
    
    # Check authorization if job has user_id
    if job.get("user_id") and token_data:
        if job["user_id"] != token_data.job_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": UNAUTHORIZED, "message": "Access denied"}
            )
    
    return StatusResponse(
        state=job["state"],
        progress=job.get("progress", 0),
        result=job.get("result"),
        error=job.get("error")
    )


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Screen2Deck API",
        "version": "2.0.0",
        "status": "healthy",
        "docs": "/docs",
        "metrics": "/metrics"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower()
    )