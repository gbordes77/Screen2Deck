"""
Refactored main application with proper security, job storage, and validation.
Production-ready FastAPI application for Screen2Deck.
"""

import asyncio
import re
import uuid
import time
from typing import Optional
from contextlib import asynccontextmanager

# Pre-compiled regex for qty detection on OCR spans (hoisted out of the
# per-request process_ocr function to avoid re-compiling on every call).
_QTY_LINE_RX = re.compile(r"^\s*(\d+|[1-9]\dx)\s+\S+")


def count_qty_lines(spans) -> int:
    """Count OCR spans that look like "<qty> <card name>" lines."""
    return sum(
        1 for s in spans if _QTY_LINE_RX.match(s["text"].strip().lower())
    )

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
from .auth import (
    TokenData,
    create_access_token,
    get_current_token,
    get_optional_token,
    require_permission,
)

# Application imports
from .telemetry import logger, new_trace, telemetry
from .models import (
    UploadResponse, StatusResponse, DeckResult, RawOCR, OCRSpan, 
    DeckSections, CardEntry, NormalizedDeck
)
from .error_taxonomy import *
from .pipeline.preprocess import preprocess_variants
from .pipeline.ocr import run_easyocr_best_of, run_vision_fallback
from .pipeline.vision_providers import run_vision_chain_structured
from .matching.fuzzy import score_candidates
from .matching.scryfall_client import SCRYFALL
from .business_rules import apply_mtgo_land_fix, validate_and_fill
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

    # Hydrate the offline Scryfall index from the bulk JSON if it is on
    # disk. This keeps cold-path fuzzy matching in-process (no network
    # call per card) and is the main unblock for the benchmark runs that
    # used to die on Scryfall rate limits.
    logger.info("Initializing Scryfall cache...")
    import os as _os

    bulk_path = getattr(settings, "SCRYFALL_BULK_PATH", None)
    if bulk_path and _os.path.exists(bulk_path):
        try:
            await asyncio.to_thread(SCRYFALL.hydrate_from_bulk, bulk_path)
            logger.info(
                "Scryfall bulk hydrated (%d names cached)",
                len(SCRYFALL.all_names()),
            )
        except Exception as exc:
            logger.warning("Scryfall bulk hydrate failed: %s", exc)
    else:
        logger.info(
            "Scryfall bulk file not found at %s; skipping hydration "
            "(run scripts/download_scryfall.py to pre-cache)",
            bulk_path,
        )
    
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
    # (scryfall_client uses requests.Session; no explicit close needed.)
    
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
    token_data: Optional[TokenData] = Depends(get_optional_token),
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
    """Run the OCR + Scryfall pipeline on uploaded image bytes.

    Two code paths live here:

    1. **Vision-primary** (``VISION_PRIMARY=true`` and Vision providers
       available): call Gemini/Claude with a JSON schema constraint,
       build DeckSections directly from the typed output, and skip
       preprocessing + EasyOCR + the regex parser entirely. This is
       the fast path — typical p95 around 2.7 s on a clean Arena
       screenshot — and the only path that lets us leverage the model
       to disambiguate split/DFC/MTGO layouts natively.

    2. **EasyOCR-primary** (legacy path, the default): the traditional
       preprocess → EasyOCR best-of → Vision fallback on low confidence
       → regex parser → Scryfall pipeline. Kicks in when Vision is
       disabled, no provider is configured, or the structured call
       returned nothing usable.
    """
    with telemetry.span("process_ocr") as span:
        span.set_attribute("job_id", job_id)

        t0 = time.time()

        # Decode image (shared by both paths)
        img = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Cannot decode image")

        await job_storage.update_job(job_id, progress=20)

        parsed: Optional[DeckSections] = None
        raw: Optional[RawOCR] = None
        ocr_method = "easyocr"

        # -------- Vision-primary fast path --------
        if settings.ENABLE_VISION_FALLBACK and getattr(settings, "VISION_PRIMARY", False):
            structured = await asyncio.to_thread(run_vision_chain_structured, img)
            if structured and (structured.get("main") or structured.get("side")):
                main_entries = [
                    CardEntry(
                        qty=c["qty"],
                        name=text_validator.sanitize_card_name(c["name"]),
                    )
                    for c in structured.get("main", [])
                ]
                side_entries = [
                    CardEntry(
                        qty=c["qty"],
                        name=text_validator.sanitize_card_name(c["name"]),
                    )
                    for c in structured.get("side", [])
                ]
                parsed = DeckSections(main=main_entries, side=side_entries)
                ocr_method = structured.get("method", "vision_structured")
                # Build a synthetic raw OCR record so downstream telemetry
                # still has something to point at.
                synthetic_spans = [
                    OCRSpan(text=f"{e.qty} {e.name}", conf=0.98)
                    for e in main_entries + side_entries
                ]
                raw = RawOCR(spans=synthetic_spans, mean_conf=0.98)
                await job_storage.update_job(job_id, progress=60)

        # -------- EasyOCR fallback / legacy path --------
        if parsed is None:
            variants = preprocess_variants(img)
            ocr_raw = run_easyocr_best_of(variants)

            await job_storage.update_job(job_id, progress=40)

            if (
                ocr_raw["mean_conf"] < settings.OCR_MIN_CONF
                or count_qty_lines(ocr_raw["spans"]) < settings.OCR_MIN_LINES
            ) and settings.ENABLE_VISION_FALLBACK:
                best_img = max(variants, key=lambda im: cv2.countNonZero(im))
                ocr_raw = run_vision_fallback(best_img)
                ocr_method = "vision_fallback_text"

            await job_storage.update_job(job_id, progress=60)

            spans = [OCRSpan(text=s["text"], conf=s["conf"]) for s in ocr_raw["spans"]]
            raw = RawOCR(spans=spans, mean_conf=ocr_raw["mean_conf"])
            parsed = parse_deck_sections(spans)

        assert parsed is not None and raw is not None  # narrow types for mypy

        await job_storage.update_job(job_id, progress=80)

        # Normalize with Scryfall (batch /cards/collection, async-wrapped)
        normalized = await normalize_deck(parsed)

        # Apply business rules (MTGO 60+15 segmentation, then sanity checks).
        # The structured Vision path already returns the 60+15 split in the
        # correct sections, so apply_mtgo_land_fix is a cheap no-op there.
        text_lines = [s.text for s in raw.spans]
        normalized = apply_mtgo_land_fix(normalized, text_lines)
        normalized = validate_and_fill(normalized)

        t1 = time.time()

        span.set_attribute("ocr.method", ocr_method)

        return DeckResult(
            jobId=job_id,
            raw=raw,
            parsed=parsed,
            normalized=normalized,
            timings_ms={"total": int((t1 - t0) * 1000)},
            traceId=trace_id,
        )


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
    """Normalize a parsed deck against Scryfall.

    Strategy:
      1. Batch every unique raw name through ``/cards/collection`` in a
         single worker thread (up to 75 identifiers per HTTP call). This
         replaces the historical N-serial ``/cards/named?fuzzy=`` loop
         that spent 60*120ms just sleeping on the rate limiter.
      2. Any name Scryfall could not resolve falls back to
         ``SCRYFALL.resolve`` (exact -> rapidfuzz offline -> online
         fuzzy), still inside the same worker thread so the FastAPI
         event loop keeps serving other requests.
    """
    from .models import NormalizedCard

    all_raw_names = sorted({e.name for e in parsed.main + parsed.side})
    if not all_raw_names:
        return NormalizedDeck(main=[], side=[])

    def _resolve_all() -> dict[str, dict]:
        resolved: dict[str, dict] = {}
        batch = SCRYFALL.batch_resolve(all_raw_names)
        for name, card in batch.items():
            resolved[name] = {
                "name": card.get("name", name),
                "id": card.get("id"),
            }

        missing = [n for n in all_raw_names if n not in resolved]
        for name in missing:
            result = SCRYFALL.resolve(name)
            resolved[name] = {
                "name": result.get("name", name),
                "id": result.get("id"),
            }
        return resolved

    resolved_map = await asyncio.to_thread(_resolve_all)

    def _to_normalized(entries: list[CardEntry]) -> list[NormalizedCard]:
        out: list[NormalizedCard] = []
        for entry in entries:
            data = resolved_map.get(entry.name, {"name": entry.name, "id": None})
            out.append(
                NormalizedCard(
                    qty=entry.qty,
                    name=data["name"],
                    scryfall_id=data["id"],
                )
            )
        return out

    return NormalizedDeck(
        main=_to_normalized(parsed.main),
        side=_to_normalized(parsed.side),
    )


@app.get(
    "/api/ocr/status/{job_id}",
    response_model=StatusResponse,
    summary="Get job status",
    description="Get the status and results of an OCR job"
)
async def get_job_status(
    job_id: str,
    token_data: Optional[TokenData] = Depends(get_optional_token),
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
            detail={"code": "JOB_NOT_FOUND", "message": "Job not found"}
        )

    # IDOR protection: a job owned by an authenticated user is only
    # visible to that user. Anonymous jobs (no user_id on the record)
    # remain fetchable by anyone holding the UUID, which preserves the
    # current anonymous upload flow.
    owner = job.get("user_id")
    if owner:
        caller = token_data.job_id if token_data else None
        if caller != owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": UNAUTHORIZED, "message": "Access denied"},
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