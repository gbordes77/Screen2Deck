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
    return sum(1 for s in spans if _QTY_LINE_RX.match(s["text"].strip().lower()))


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
from .core.idempotency import generate_job_key
from .core.metrics_minimal import (
    create_metrics_app,
    track_ocr_request,
    record_cache_access,
)
from .auth import (
    TokenData,
    get_optional_token,
)

# Application imports
from .telemetry import logger, new_trace, telemetry
from .models import (
    UploadResponse,
    StatusResponse,
    DeckResult,
    RawOCR,
    OCRSpan,
    DeckSections,
    CardEntry,
    NormalizedDeck,
)
from .error_taxonomy import *
from .pipeline.preprocess import preprocess_variants
from .pipeline.ocr import run_easyocr_best_of, run_vision_fallback
from .pipeline.vision_providers import run_vision_chain_structured
from .matching.scryfall_client import SCRYFALL
from .business_rules import apply_mtgo_land_fix, validate_and_fill
from .routers import health, auth_router, export_router

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
    version="2.4.0",
    description="Production-ready MTG card list OCR and export API",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# Add security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    AuthMiddleware,
    skip_auth_paths={
        "/",
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
    },
)

# Configure CORS with settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
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
    description="Upload a deck list image for OCR processing with idempotency support",
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
                detail={"code": VALIDATION_ERROR, "message": "Invalid request headers"},
            )

        # Validate and sanitize image
        try:
            sanitized_content, metadata = await image_validator.validate_upload(
                file, calculate_hash=True
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": BAD_IMAGE, "message": "Image validation failed"},
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
                "superres": False,
            },
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
        # Attach caller identity when available so ownership can be enforced
        # on /api/ocr/status/{job_id}. Anonymous uploads stay anonymous.
        user_id = token_data.user_id if token_data else None

        await job_storage.create_job(
            job_id=job_id, image_hash=image_hash, user_id=user_id, metadata=metadata
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
                job_id, state="completed", progress=100, result=result.model_dump()
            )

        except Exception as e:
            logger.error(f"OCR processing failed for job {job_id}: {e}")
            await job_storage.update_job(
                job_id, state="failed", progress=100, error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": OCR_ERROR, "message": "OCR processing failed"},
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
        if settings.ENABLE_VISION_FALLBACK and getattr(
            settings, "VISION_PRIMARY", False
        ):
            try:
                structured = await asyncio.to_thread(run_vision_chain_structured, img)
            except Exception as vision_exc:
                logger.warning("Vision-primary chain failed: %s", vision_exc)
                structured = None
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
            # Both ``preprocess_variants`` (OpenCV) and
            # ``run_easyocr_best_of`` (PyTorch) are CPU-bound and
            # historically ran inline on the event loop, blocking every
            # other request — including ``/health`` — for the full
            # duration of the OCR pass. Ship them off to a worker
            # thread so concurrent uploads and health checks keep
            # flowing while a scan is in flight.
            def _cpu_bound_ocr():
                vars_ = preprocess_variants(img)
                raw_ = run_easyocr_best_of(vars_)
                return vars_, raw_

            variants, ocr_raw = await asyncio.to_thread(_cpu_bound_ocr)

            await job_storage.update_job(job_id, progress=40)

            if (
                ocr_raw["mean_conf"] < settings.OCR_MIN_CONF
                or count_qty_lines(ocr_raw["spans"]) < settings.OCR_MIN_LINES
            ) and settings.ENABLE_VISION_FALLBACK:
                best_img = max(
                    variants,
                    key=lambda im: cv2.countNonZero(
                        cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
                        if len(im.shape) == 3
                        else im
                    ),
                )
                ocr_raw = await asyncio.to_thread(run_vision_fallback, best_img)
                ocr_method = "vision_fallback_text"

            await job_storage.update_job(job_id, progress=60)

            spans = [
                OCRSpan(text=s["text"], conf=s["conf"], bbox=s.get("bbox"))
                for s in ocr_raw["spans"]
            ]
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


_QTY_TOKEN_RX = re.compile(r"^\s*[xX]?\s*(\d{1,2})\s*[xX]?\s*$")
_INLINE_QTY_RX = re.compile(r"^\s*(\d{1,2}|[xX]\d{1,2})\s+(.+?)\s*$")

# UI chrome strings that Arena / MTGO / mtggoldfish render next to deck
# lists. These are NOT card names — filtering them out stops the parser
# from emitting bogus entries like ``40x "700"`` (from the ``60/60
# Cards`` stats label) or ``15x "Cards"`` (from the sideboard header).
_UI_CHROME_RX = re.compile(
    r"^\s*("
    r"\d+\s*/\s*\d+"                     # 60/60, 15/15, …
    r"|\d+\s*cards?"                      # "60 Cards", "15 Cards"
    r"|cards?|deck|sideboard|mainboard"   # bare UI labels
    r"|collection|library|graveyard|hand"
    r"|commander|companion|maybe(board)?"
    r"|remove|add|close|save|export|edit"
    r"|creatures?|lands?|spells?|planes?walkers?|artifacts?|enchantments?"
    r"|search|filter|sort|price|total"
    r"|\d+%|~\d+|\d+\s*mana"
    r")\s*$",
    re.IGNORECASE,
)

# Known Scryfall names (hydrated at startup) that we intentionally never
# blocklist — e.g. "Forest", "Creature — Beast". We only apply the chrome
# filter to strings that *also* look like UI noise; real card names like
# "Forest" go through untouched because ``_UI_CHROME_RX`` doesn't match
# anything that isn't in its closed list.


def _looks_like_ui_chrome(text: str) -> bool:
    return bool(_UI_CHROME_RX.match(text.strip()))


def _span_center_y(span: OCRSpan) -> Optional[float]:
    if not span.bbox:
        return None
    ys = [pt[1] for pt in span.bbox]
    return sum(ys) / len(ys) if ys else None


def _span_left_x(span: OCRSpan) -> Optional[float]:
    if not span.bbox:
        return None
    xs = [pt[0] for pt in span.bbox]
    return min(xs) if xs else None


def _span_height(span: OCRSpan) -> float:
    if not span.bbox:
        return 0.0
    ys = [pt[1] for pt in span.bbox]
    return max(ys) - min(ys) if ys else 0.0


def _match_qty_token(text: str) -> Optional[int]:
    """Return the integer quantity when ``text`` is a pure qty token.

    Matches ``"4"``, ``"x2"``, ``"X3"``, ``" 4x "`` — anything that is
    *only* a small integer with an optional ``x`` prefix/suffix. Returns
    None for text that also carries a card name.
    """
    m = _QTY_TOKEN_RX.match(text)
    if not m:
        return None
    qty = int(m.group(1))
    if 1 <= qty <= 99:
        return qty
    return None


def _strip_leading_ui_noise(name: str) -> str:
    """Drop UI characters that EasyOCR picks up from MTGA card frames.

    Arena overlays brackets / parentheses / pipe glyphs on card tiles.
    The regex below trims any stray leading punctuation so the Scryfall
    fuzzy matcher gets a clean starting token.
    """
    return re.sub(r"^[\s\(\[\{\|\.\,\:\;\-]+", "", name).strip()


def parse_deck_sections(spans: list[OCRSpan]) -> DeckSections:
    """Parse OCR spans into deck sections.

    Two layouts coexist in the wild and we handle both:

    1. **Inline / text-export layout** (MTGO exports, mtggoldfish text
       dumps, and MTGA's "Export deck" clipboard format): each OCR span
       already reads ``"4 Lightning Bolt"``. We match via
       ``_INLINE_QTY_RX`` on the span text — this is the legacy
       behaviour and stays fast.

    2. **Visual / column-separated layout** (the actual Arena deck
       builder UI — what the MTG community screenshots the most): the
       quantity and the card name are in *different columns*, so
       EasyOCR emits them as two separate spans. We fall back to a
       **spatial parser** that pairs each standalone ``"x2"`` / ``"3"``
       qty span with the closest-by-y card-name span on the same row.

    The spatial parser only activates when the inline pass yields too
    few cards — that way clean text exports don't pay its cost.
    """
    main_entries: list[CardEntry] = []
    side_entries: list[CardEntry] = []
    section = "main"

    # --- Pass 1: inline "<qty> <name>" parsing (legacy behaviour) ---
    consumed_span_ids: set[int] = set()
    for idx, span in enumerate(spans):
        line = span.text.strip()
        if not line:
            continue
        if line.lower().startswith("sideboard") or line.lower().startswith("sb"):
            section = "side"
            consumed_span_ids.add(idx)
            continue
        # Drop pure UI chrome lines before we try to parse a qty out of
        # them. Things like ``"60/60 Cards"`` or ``"15 Cards"`` would
        # otherwise feed the regex and produce bogus entries.
        if _looks_like_ui_chrome(line):
            consumed_span_ids.add(idx)
            continue
        m = _INLINE_QTY_RX.match(line)
        if m:
            qty_raw = m.group(1)
            name = m.group(2)
            qty = int(qty_raw.lstrip("xX")) if qty_raw else 0
            if qty <= 0:
                continue
            clean_name = _strip_leading_ui_noise(name)
            clean_name = text_validator.sanitize_card_name(clean_name)
            if not clean_name or _looks_like_ui_chrome(clean_name):
                continue
            entry = CardEntry(qty=qty, name=clean_name)
            (main_entries if section == "main" else side_entries).append(entry)
            consumed_span_ids.add(idx)

    # --- Pass 2: spatial pairing for MTGA visual layouts ---
    # If the inline pass captured fewer than 10 cards AND bboxes are
    # available, attempt to pair qty-only spans with name-only spans
    # by vertical alignment.
    if (len(main_entries) + len(side_entries)) < 10 and any(
        s.bbox for s in spans
    ):
        paired = _spatial_pair(
            [s for i, s in enumerate(spans) if i not in consumed_span_ids]
        )
        # Insert paired entries respecting the most-recently-seen
        # "Sideboard" marker. The spatial pass resets section to
        # "main" since it doesn't know about markers; we keep that
        # simple — the validator will redistribute 60+15 afterwards.
        main_entries.extend(e for e in paired if e.qty > 0)

    return DeckSections(main=main_entries, side=side_entries)


def _spatial_pair(spans: list[OCRSpan]) -> list[CardEntry]:
    """Pair standalone qty spans with the nearest card-name span.

    Strategy:
        * Bucket every span with a bbox into rows by center-y. Row
          tolerance is derived from the median span height so it
          adapts to resolution.
        * Within a row, the left-most readable text span is the
          candidate card name, and any ``"x?<n>"``-shaped span is the
          quantity. When a row has one qty and one or more name spans,
          emit a ``CardEntry``.
        * Rows with no detected qty or no readable name are dropped.

    This approximates what the human eye does when scanning the Arena
    deck-builder: "this number belongs to that card because they share
    a horizontal line."
    """
    usable = [s for s in spans if s.bbox and _span_center_y(s) is not None]
    if not usable:
        return []

    # Row tolerance = 0.6 × median span height (empirically ~12-18 px
    # on a 1080p Arena screenshot).
    heights = sorted(h for h in (_span_height(s) for s in usable) if h > 0)
    row_tol = heights[len(heights) // 2] * 0.6 if heights else 12.0

    # Sort spans top-down, then cluster into rows.
    usable_sorted = sorted(usable, key=lambda s: _span_center_y(s) or 0.0)
    rows: list[list[OCRSpan]] = []
    for span in usable_sorted:
        cy = _span_center_y(span) or 0.0
        if rows and abs(cy - (_span_center_y(rows[-1][0]) or 0.0)) <= row_tol:
            rows[-1].append(span)
        else:
            rows.append([span])

    entries: list[CardEntry] = []
    for row in rows:
        qty = None
        name_candidates: list[OCRSpan] = []
        for s in row:
            text = s.text.strip()
            if _looks_like_ui_chrome(text):
                continue
            as_qty = _match_qty_token(text)
            if as_qty is not None:
                qty = as_qty
                continue
            # Ignore obvious noise (pure punctuation, very short strings
            # that are neither qty nor a word).
            if len(re.sub(r"[^a-zA-Z]", "", text)) < 3:
                continue
            name_candidates.append(s)

        if qty is None or not name_candidates:
            continue

        # Pick the left-most name candidate as the card name — MTGA and
        # MTGO both render the name flush-left while the qty sits
        # further right on the same row.
        name_span = min(
            name_candidates,
            key=lambda s: _span_left_x(s) if _span_left_x(s) is not None else 1e9,
        )
        raw_name = _strip_leading_ui_noise(name_span.text)
        clean_name = text_validator.sanitize_card_name(raw_name)
        if not clean_name or _looks_like_ui_chrome(clean_name):
            continue
        entries.append(CardEntry(qty=qty, name=clean_name))
    return entries


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
    description="Get the status and results of an OCR job",
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
            detail={"code": VALIDATION_ERROR, "message": "Invalid job ID format"},
        )

    # Get job from storage
    job = await job_storage.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": "Job not found"},
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
        error=job.get("error"),
    )


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Screen2Deck API",
        "version": "2.4.0",
        "status": "healthy",
        "docs": "/docs",
        "metrics": "/metrics",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
    )
