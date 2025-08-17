import uuid, hashlib, time, re
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
import numpy as np, cv2
from .config import get_settings
from .telemetry import logger, new_trace
from .models import UploadResponse, StatusResponse, DeckResult, RawOCR, OCRSpan, DeckSections, CardEntry, CardCandidate, NormalizedDeck, NormalizedCard
from .error_taxonomy import *
from .pipeline.preprocess import preprocess_variants
from .pipeline.ocr import run_easyocr_best_of, run_vision_fallback
from .matching.fuzzy import score_candidates
from .matching.scryfall_client import SCRYFALL
from .business_rules import apply_mtgo_land_fix, validate_and_fill
from . import cache

S = get_settings()
app = FastAPI(default_response_class=ORJSONResponse)
# Fix CORS: Restrict to specific origins for security
allowed_origins = [
    "http://localhost:3000",  # Next.js dev server
    "http://localhost:3001",  # Alternative port
    "https://screen2deck.com",  # Production domain (adjust as needed)
]
app.add_middleware(
    CORSMiddleware, 
    allow_origins=allowed_origins,  # Specific origins only
    allow_credentials=True, 
    allow_methods=["GET", "POST"],  # Only methods we actually use
    allow_headers=["*"]
)

# Improved per-IP rate limiting with configurable limits
_last_req: Dict[str, float] = {}
def _rate_limit(request: Request, min_interval=0.5, max_requests_per_minute=30):
    """Rate limit requests per IP address.
    
    Args:
        request: FastAPI request object to extract client IP
        min_interval: Minimum seconds between requests (default 0.5s)
        max_requests_per_minute: Maximum requests per minute per IP
    """
    # Get real client IP (considering proxy headers)
    client_ip = request.client.host
    if "X-Forwarded-For" in request.headers:
        client_ip = request.headers["X-Forwarded-For"].split(",")[0].strip()
    elif "X-Real-IP" in request.headers:
        client_ip = request.headers["X-Real-IP"]
    
    now = time.time()
    if client_ip in _last_req and now - _last_req[client_ip] < min_interval:
        raise HTTPException(
            status_code=429, 
            detail={"code": RATE_LIMIT, "message": f"Too many requests. Please wait {min_interval}s between requests."}
        )
    _last_req[client_ip] = now
    
    # Clean old entries to prevent memory leak (older than 1 minute)
    cutoff = now - 60
    _last_req.clear()
    _last_req.update({k: v for k, v in _last_req.items() if v > cutoff})

@app.post("/api/ocr/upload", response_model=UploadResponse)
async def upload_image(request: Request, file: UploadFile = File(...)):
    _rate_limit(request)  # Per-IP rate limiting
    traceId = new_trace()
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, detail={"code": BAD_IMAGE, "message": "Unsupported content type"})
    content = await file.read()
    if len(content) > S.MAX_IMAGE_MB * 1024 * 1024:
        raise HTTPException(413, detail={"code": BAD_IMAGE, "message": "Image too large"})

    jobId = str(uuid.uuid4())
    img = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, detail={"code": BAD_IMAGE, "message": "Cannot decode image"})

    t0 = time.time()
    # Multi-pass OCR (best-of)
    variants = preprocess_variants(img)
    ocr_raw = run_easyocr_best_of(variants)

    # Gate: si douteux, fallback Vision si activé
    def count_qty_lines(spans):
        rx = re.compile(r"^\\s*(\\d+|[1-9]\\dx)\\s+\\S+")
        return sum(1 for s in spans if rx.match(s["text"].strip().lower()))
    if (ocr_raw["mean_conf"] < S.OCR_MIN_CONF or count_qty_lines(ocr_raw["spans"]) < S.OCR_MIN_LINES) and S.ENABLE_VISION_FALLBACK:
        best_img = max(variants, key=lambda im: cv2.countNonZero(im))
        ocr_raw = run_vision_fallback(best_img)

    spans = [OCRSpan(text=s["text"], conf=s["conf"]) for s in ocr_raw["spans"]]
    raw = RawOCR(spans=spans, mean_conf=ocr_raw["mean_conf"])

    text_lines = [s.text for s in spans]
    main_entries: List[CardEntry] = []; side_entries: List[CardEntry] = []
    section = "main"
    for line in text_lines:
        l = line.strip()
        if l.lower().startswith("sideboard") or l.lower().startswith("sb"):
            section = "side"; continue
        qty = 0; name = ""
        parts = l.split(" ", 1)
        if len(parts) == 2 and parts[0].isdigit():
            qty = int(parts[0]); name = parts[1]
        elif len(parts) == 2 and parts[0].lower().endswith("x") and parts[0][:-1].isdigit():
            qty = int(parts[0][:-1]); name = parts[1]
        if qty > 0 and name:
            (main_entries if section=="main" else side_entries).append(CardEntry(qty=qty, name=name))

    parsed = DeckSections(main=main_entries, side=side_entries)

    # Suggestions fuzzy locales (UI) + Résolution canonique Scryfall (OBLIGATOIRE)
    names = SCRYFALL.all_names()
    def enrich(entries: List[CardEntry]):
        out = []
        for e in entries:
            cands_local = score_candidates(e.name, names, limit=S.FUZZY_MATCH_TOPK) if names else []
            resolved = SCRYFALL.resolve(e.name, topk=S.FUZZY_MATCH_TOPK) if S.ALWAYS_VERIFY_SCRYFALL else {"name": e.name, "id": None, "candidates": []}
            merged = []
            seen = set()
            for cand, sc in cands_local:
                if cand not in seen: merged.append(CardCandidate(name=cand, score=sc)); seen.add(cand)
            for c in resolved.get("candidates", []):
                n = c["name"]
                if n not in seen: merged.append(CardCandidate(name=n, score=c.get("score",0.0))); seen.add(n)
            out.append(CardEntry(qty=e.qty, name=resolved["name"], candidates=merged))
        return out

    parsed = DeckSections(main=enrich(parsed.main), side=enrich(parsed.side))

    # Normalisation finale (attache scryfall_id)
    def to_norm(entries: List[CardEntry]) -> List[NormalizedCard]:
        res = []
        for e in entries:
            exact = SCRYFALL.lookup_by_name(e.name)
            sid = exact[0]["id"] if exact else None
            res.append(NormalizedCard(qty=e.qty, name=e.name, scryfall_id=sid))
        return res

    normalized = NormalizedDeck(main=to_norm(parsed.main), side=to_norm(parsed.side))
    normalized = validate_and_fill(normalized)

    t1 = time.time()
    result = DeckResult(jobId=jobId, raw=raw, parsed=parsed, normalized=normalized, timings_ms={"total": int((t1-t0)*1000)}, traceId=new_trace())
    await cache.set_job(jobId, {"state":"completed","result": result.model_dump()})
    return UploadResponse(jobId=jobId)

@app.get("/api/ocr/status/{jobId}", response_model=StatusResponse)
async def status(jobId: str):
    v = await cache.get_job(jobId)
    if not v: return StatusResponse(state="queued", progress=5)
    if v.get("state") == "completed": return StatusResponse(state="completed", progress=100, result=v["result"])
    if v.get("state") == "failed": return StatusResponse(state="failed", progress=100, error=v.get("error"))
    return StatusResponse(state="processing", progress=50)

from .exporters.mtga import export_mtga
from .exporters.moxfield import export_moxfield
from .exporters.archidekt import export_archidekt
from .exporters.tappedout import export_tappedout

@app.post("/api/export/{target}")
async def export_deck(target: str, deck: NormalizedDeck):
    if   target=="mtga":      text = export_mtga(deck)
    elif target=="moxfield":  text = export_moxfield(deck)
    elif target=="archidekt": text = export_archidekt(deck)
    elif target=="tappedout": text = export_tappedout(deck)
    else: raise HTTPException(400, detail={"code": EXPORT_INVALID, "message": "Unknown target"})
    return {"text": text}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=S.PORT)