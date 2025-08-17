"""
OCR Service - Business logic for OCR processing.
Abstracts OCR operations from API endpoints.
"""

import hashlib
import time
from typing import Dict, List, Optional, Tuple
import numpy as np
import cv2
import re

from ..config import get_settings
from ..models import (
    RawOCR, OCRSpan, DeckSections, CardEntry, 
    CardCandidate, NormalizedCard, NormalizedDeck, DeckResult
)
from ..pipeline.preprocess import preprocess_variants
from ..pipeline.ocr import run_easyocr_best_of, run_vision_fallback
from ..matching.fuzzy import score_candidates
from ..matching.scryfall_client import SCRYFALL
from ..business_rules import apply_mtgo_land_fix, validate_and_fill
from ..cache_manager import cache_manager, cached
from ..telemetry import logger
from ..error_taxonomy import OCR_FAILED, VALIDATION_FAILED

S = get_settings()

class OCRService:
    """Service for OCR processing operations."""
    
    def __init__(self):
        """Initialize OCR service."""
        self.scryfall = SCRYFALL
        self.cache = cache_manager
    
    def hash_image(self, image_data: bytes) -> str:
        """Generate hash for image data."""
        return hashlib.sha256(image_data).hexdigest()
    
    def process_image(self, image_data: bytes, job_id: str, trace_id: str) -> DeckResult:
        """
        Process image through complete OCR pipeline.
        
        Args:
            image_data: Raw image bytes
            job_id: Unique job identifier
            trace_id: Trace ID for logging
            
        Returns:
            DeckResult with processed deck information
            
        Raises:
            ValueError: If image cannot be decoded
            RuntimeError: If OCR processing fails
        """
        # Check cache first
        image_hash = self.hash_image(image_data)
        cached_result = self.cache.get_ocr_result(image_hash)
        if cached_result:
            logger.info(f"Cache hit for job {job_id}")
            cached_result["jobId"] = job_id
            cached_result["traceId"] = trace_id
            return DeckResult(**cached_result)
        
        # Decode image
        img = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Cannot decode image")
        
        # Track timings
        timings = {}
        
        # Preprocessing
        t0 = time.time()
        variants = preprocess_variants(img)
        timings["preprocess"] = (time.time() - t0) * 1000
        
        # OCR processing
        t1 = time.time()
        ocr_raw = self._perform_ocr(variants)
        timings["ocr"] = (time.time() - t1) * 1000
        
        # Parse cards from OCR text
        raw = self._create_raw_ocr(ocr_raw)
        parsed = self._parse_cards(raw.spans)
        
        # Validate and enrich with Scryfall
        t2 = time.time()
        parsed = self._enrich_with_scryfall(parsed)
        normalized = self._normalize_deck(parsed)
        
        # Apply business rules
        text_lines = [s.text for s in raw.spans]
        normalized = apply_mtgo_land_fix(normalized, text_lines)
        normalized = validate_and_fill(normalized)
        timings["scryfall"] = (time.time() - t2) * 1000
        
        timings["total"] = sum(timings.values())
        
        # Create result
        result = DeckResult(
            jobId=job_id,
            raw=raw,
            parsed=parsed,
            normalized=normalized,
            timings_ms=timings,
            traceId=trace_id
        )
        
        # Cache result
        self.cache.cache_ocr_result(image_hash, result.dict(), ttl=3600)
        
        return result
    
    def _perform_ocr(self, variants: List[np.ndarray]) -> Dict:
        """
        Perform OCR on image variants.
        
        Args:
            variants: List of preprocessed image variants
            
        Returns:
            OCR results dictionary
        """
        ocr_raw = run_easyocr_best_of(variants)
        
        # Check if fallback is needed
        if self._should_use_fallback(ocr_raw):
            logger.info("OCR confidence low, using fallback")
            best_img = max(variants, key=lambda im: cv2.countNonZero(im))
            ocr_raw = run_vision_fallback(best_img)
        
        return ocr_raw
    
    def _should_use_fallback(self, ocr_raw: Dict) -> bool:
        """Check if Vision fallback should be used."""
        if not S.ENABLE_VISION_FALLBACK:
            return False
        
        # Check confidence
        if ocr_raw["mean_conf"] < S.OCR_MIN_CONF:
            return True
        
        # Check line count
        qty_lines = self._count_quantity_lines(ocr_raw["spans"])
        if qty_lines < S.OCR_MIN_LINES:
            return True
        
        return False
    
    def _count_quantity_lines(self, spans: List[Dict]) -> int:
        """Count lines that look like card entries."""
        rx = re.compile(r"^\s*(\d+|[1-9]\dx)\s+\S+")
        return sum(1 for s in spans if rx.match(s["text"].strip().lower()))
    
    def _create_raw_ocr(self, ocr_raw: Dict) -> RawOCR:
        """Create RawOCR model from OCR results."""
        spans = [
            OCRSpan(text=s["text"], conf=s["conf"]) 
            for s in ocr_raw["spans"]
        ]
        return RawOCR(spans=spans, mean_conf=ocr_raw["mean_conf"])
    
    def _parse_cards(self, spans: List[OCRSpan]) -> DeckSections:
        """
        Parse card entries from OCR spans.
        
        Args:
            spans: List of OCR text spans
            
        Returns:
            DeckSections with mainboard and sideboard entries
        """
        main_entries = []
        side_entries = []
        section = "main"
        
        for span in spans:
            line = span.text.strip()
            
            # Check for sideboard marker
            if line.lower().startswith(("sideboard", "sb")):
                section = "side"
                continue
            
            # Parse card entry
            entry = self._parse_card_line(line)
            if entry:
                if section == "main":
                    main_entries.append(entry)
                else:
                    side_entries.append(entry)
        
        return DeckSections(main=main_entries, side=side_entries)
    
    def _parse_card_line(self, line: str) -> Optional[CardEntry]:
        """Parse a single card line."""
        parts = line.split(" ", 1)
        if len(parts) != 2:
            return None
        
        qty_str, name = parts
        
        # Parse quantity
        qty = 0
        if qty_str.isdigit():
            qty = int(qty_str)
        elif qty_str.lower().endswith("x") and qty_str[:-1].isdigit():
            qty = int(qty_str[:-1])
        
        if qty > 0 and name:
            return CardEntry(qty=qty, name=name)
        
        return None
    
    @cached(prefix="scryfall_enrich", ttl=7200)
    def _enrich_with_scryfall(self, parsed: DeckSections) -> DeckSections:
        """Enrich parsed deck with Scryfall data."""
        return DeckSections(
            main=self._enrich_entries(parsed.main),
            side=self._enrich_entries(parsed.side)
        )
    
    def _enrich_entries(self, entries: List[CardEntry]) -> List[CardEntry]:
        """Enrich card entries with Scryfall validation."""
        enriched = []
        names = self.scryfall.all_names()
        
        for entry in entries:
            # Local fuzzy matching
            candidates_local = []
            if names:
                # Check cache first
                cached_fuzzy = self.cache.get_fuzzy_match(entry.name)
                if cached_fuzzy:
                    candidates_local = cached_fuzzy
                else:
                    candidates_local = score_candidates(entry.name, names, limit=S.FUZZY_MATCH_TOPK)
                    self.cache.cache_fuzzy_match(entry.name, candidates_local)
            
            # Scryfall resolution
            resolved = {"name": entry.name, "id": None, "candidates": []}
            if S.ALWAYS_VERIFY_SCRYFALL:
                # Check cache first
                cached_card = self.cache.get_scryfall_card(entry.name)
                if cached_card:
                    resolved = cached_card
                else:
                    resolved = self.scryfall.resolve(entry.name, topk=S.FUZZY_MATCH_TOPK)
                    self.cache.cache_scryfall_card(entry.name, resolved)
            
            # Merge candidates
            merged = self._merge_candidates(candidates_local, resolved.get("candidates", []))
            
            enriched.append(CardEntry(
                qty=entry.qty,
                name=resolved["name"],
                candidates=merged
            ))
        
        return enriched
    
    def _merge_candidates(self, local: List[Tuple], scryfall: List[Dict]) -> List[CardCandidate]:
        """Merge local and Scryfall candidates."""
        merged = []
        seen = set()
        
        # Add local candidates
        for name, score in local:
            if name not in seen:
                merged.append(CardCandidate(name=name, score=score))
                seen.add(name)
        
        # Add Scryfall candidates
        for candidate in scryfall:
            name = candidate["name"]
            if name not in seen:
                merged.append(CardCandidate(
                    name=name,
                    score=candidate.get("score", 0.0)
                ))
                seen.add(name)
        
        return merged
    
    def _normalize_deck(self, parsed: DeckSections) -> NormalizedDeck:
        """Normalize deck with Scryfall IDs."""
        return NormalizedDeck(
            main=self._normalize_entries(parsed.main),
            side=self._normalize_entries(parsed.side)
        )
    
    def _normalize_entries(self, entries: List[CardEntry]) -> List[NormalizedCard]:
        """Normalize card entries with Scryfall IDs."""
        normalized = []
        
        for entry in entries:
            # Lookup Scryfall ID
            scryfall_id = None
            cards = self.scryfall.lookup_by_name(entry.name)
            if cards:
                scryfall_id = cards[0].get("id")
            
            normalized.append(NormalizedCard(
                qty=entry.qty,
                name=entry.name,
                scryfall_id=scryfall_id
            ))
        
        return normalized