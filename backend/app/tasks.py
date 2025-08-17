"""
Celery tasks for async OCR processing.
Handles background job processing with Redis as broker.
"""

from celery import Celery
from typing import Dict, Any
import time
import numpy as np
import cv2
from .config import get_settings
from .pipeline.preprocess import preprocess_variants
from .pipeline.ocr import run_easyocr_best_of, run_vision_fallback
from .matching.fuzzy import score_candidates
from .matching.scryfall_client import SCRYFALL
from .models import RawOCR, OCRSpan, DeckSections, CardEntry, CardCandidate, NormalizedCard, NormalizedDeck
from .business_rules import apply_mtgo_land_fix, validate_and_fill
from .telemetry import logger
import redis
import json
import re

S = get_settings()

# Initialize Celery
celery_app = Celery(
    'screen2deck',
    broker=str(S.REDIS_URL),
    backend=str(S.REDIS_URL),
    include=['app.tasks']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30,  # 30 seconds max per task
    task_soft_time_limit=25,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)

# Redis client for job status
redis_client = redis.from_url(str(S.REDIS_URL)) if S.USE_REDIS else None

def update_job_status(job_id: str, status: str, progress: int = 0, result: Dict = None, error: str = None):
    """Update job status in Redis."""
    if not redis_client:
        return
    
    job_data = {
        "state": status,
        "progress": progress,
        "timestamp": time.time()
    }
    
    if result:
        job_data["result"] = result
    if error:
        job_data["error"] = error
    
    # Store with 1 hour TTL
    redis_client.setex(
        f"job:{job_id}",
        3600,
        json.dumps(job_data)
    )

def get_job_status(job_id: str) -> Dict:
    """Get job status from Redis."""
    if not redis_client:
        return {"state": "unknown"}
    
    data = redis_client.get(f"job:{job_id}")
    if data:
        return json.loads(data)
    return {"state": "not_found"}

@celery_app.task(bind=True, name='process_ocr')
def process_ocr_task(self, job_id: str, image_data: bytes) -> Dict:
    """
    Async OCR processing task.
    
    Args:
        job_id: Unique job identifier
        image_data: Image bytes
        
    Returns:
        Processed deck result
    """
    try:
        # Update status: processing
        update_job_status(job_id, "processing", 10)
        
        # Decode image
        img = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Cannot decode image")
        
        update_job_status(job_id, "processing", 20)
        
        # Preprocessing
        t0 = time.time()
        variants = preprocess_variants(img)
        preprocess_time = (time.time() - t0) * 1000
        
        update_job_status(job_id, "processing", 40)
        
        # OCR with best-of strategy
        t1 = time.time()
        ocr_raw = run_easyocr_best_of(variants)
        
        # Fallback to Vision if confidence is low
        def count_qty_lines(spans):
            rx = re.compile(r"^\\s*(\\d+|[1-9]\\dx)\\s+\\S+")
            return sum(1 for s in spans if rx.match(s["text"].strip().lower()))
        
        if (ocr_raw["mean_conf"] < S.OCR_MIN_CONF or 
            count_qty_lines(ocr_raw["spans"]) < S.OCR_MIN_LINES) and S.ENABLE_VISION_FALLBACK:
            best_img = max(variants, key=lambda im: cv2.countNonZero(im))
            ocr_raw = run_vision_fallback(best_img)
        
        ocr_time = (time.time() - t1) * 1000
        
        update_job_status(job_id, "processing", 60)
        
        # Parse cards
        spans = [OCRSpan(text=s["text"], conf=s["conf"]) for s in ocr_raw["spans"]]
        raw = RawOCR(spans=spans, mean_conf=ocr_raw["mean_conf"])
        
        text_lines = [s.text for s in spans]
        main_entries = []
        side_entries = []
        section = "main"
        
        for line in text_lines:
            l = line.strip()
            if l.lower().startswith("sideboard") or l.lower().startswith("sb"):
                section = "side"
                continue
            
            qty = 0
            name = ""
            parts = l.split(" ", 1)
            
            if len(parts) == 2 and parts[0].isdigit():
                qty = int(parts[0])
                name = parts[1]
            elif len(parts) == 2 and parts[0].lower().endswith("x") and parts[0][:-1].isdigit():
                qty = int(parts[0][:-1])
                name = parts[1]
            
            if qty > 0 and name:
                if section == "main":
                    main_entries.append(CardEntry(qty=qty, name=name))
                else:
                    side_entries.append(CardEntry(qty=qty, name=name))
        
        update_job_status(job_id, "processing", 80)
        
        # Scryfall validation
        t2 = time.time()
        parsed = DeckSections(main=main_entries, side=side_entries)
        
        # Fuzzy matching and Scryfall resolution
        names = SCRYFALL.all_names()
        
        def enrich(entries):
            out = []
            for e in entries:
                cands_local = score_candidates(e.name, names, limit=S.FUZZY_MATCH_TOPK) if names else []
                resolved = SCRYFALL.resolve(e.name, topk=S.FUZZY_MATCH_TOPK) if S.ALWAYS_VERIFY_SCRYFALL else {
                    "name": e.name, "id": None, "candidates": []
                }
                
                merged = []
                seen = set()
                for cand, sc in cands_local:
                    if cand not in seen:
                        merged.append(CardCandidate(name=cand, score=sc))
                        seen.add(cand)
                
                for c in resolved.get("candidates", []):
                    n = c["name"]
                    if n not in seen:
                        merged.append(CardCandidate(name=n, score=c.get("score", 0.0)))
                        seen.add(n)
                
                out.append(CardEntry(qty=e.qty, name=resolved["name"], candidates=merged))
            return out
        
        parsed = DeckSections(main=enrich(parsed.main), side=enrich(parsed.side))
        
        # Normalize
        def to_norm(entries):
            res = []
            for e in entries:
                sid = SCRYFALL.lookup_by_name(e.name)[0].get("id") if SCRYFALL.lookup_by_name(e.name) else None
                res.append(NormalizedCard(qty=e.qty, name=e.name, scryfall_id=sid))
            return res
        
        normalized = NormalizedDeck(main=to_norm(parsed.main), side=to_norm(parsed.side))
        
        # Apply business rules
        normalized = apply_mtgo_land_fix(normalized, text_lines)
        normalized = validate_and_fill(normalized)
        
        scryfall_time = (time.time() - t2) * 1000
        
        # Prepare result
        result = {
            "jobId": job_id,
            "raw": raw.dict(),
            "parsed": parsed.dict(),
            "normalized": normalized.dict(),
            "timings_ms": {
                "preprocess": preprocess_time,
                "ocr": ocr_time,
                "scryfall": scryfall_time,
                "total": preprocess_time + ocr_time + scryfall_time
            },
            "traceId": f"celery-{job_id}"
        }
        
        # Update status: completed
        update_job_status(job_id, "completed", 100, result)
        
        logger.info(f"OCR job {job_id} completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"OCR job {job_id} failed: {str(e)}")
        update_job_status(job_id, "failed", 0, error=str(e))
        raise