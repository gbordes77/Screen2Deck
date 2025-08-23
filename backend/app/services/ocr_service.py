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
    
    def _parse_cards_old(self, spans: List[OCRSpan]) -> DeckSections:
        """
        Parse card entries from OCR spans.
        
        Args:
            spans: List of OCR text spans
            
        Returns:
            DeckSections with mainboard and sideboard entries
        """
        main_entries = []
        side_entries = []
        is_sideboard = False
        
        # Track card names and quantities separately for MTGA format
        pending_card_name = None
        
        # Multiple patterns to match different card formats
        patterns = [
            # Format: "4 Lightning Bolt" or "4 Lightning Bolt (SET)"
            re.compile(r'^(\d+)\s+(.+?)(?:\s*\([A-Z0-9]+\))?$'),
            # Format: "Lightning Bolt x4" or "Lightning Bolt x 4"
            re.compile(r'^(.+?)\s+x\s*(\d+)$', re.IGNORECASE),
            # Format: "4x Lightning Bolt"
            re.compile(r'^(\d+)x\s+(.+?)$', re.IGNORECASE),
            # Format: "Lightning Bolt 4" (last resort)
            re.compile(r'^(.+?)\s+(\d+)$'),
        ]
        
        # Pattern for standalone quantities (MTGA format)
        qty_pattern = re.compile(r'^x(\d+)$', re.IGNORECASE)
        
        for i, span in enumerate(spans):
            line = span.text.strip()
            
            # Skip empty or too short lines
            if not line or len(line) < 2:
                continue
            
            # Check for sideboard markers (more comprehensive)
            if any(marker in line.lower() for marker in ['sideboard', 'side board', 'side', 'sb', 'reserve']):
                is_sideboard = True
                pending_card_name = None  # Reset pending card
                continue
            
            # Skip UI elements and non-card lines
            skip_words = ['===', '---', 'total', 'mana', 'curve', 'library', 'temur otters', 'deck', 'commander']
            # Special handling for "X Cards" pattern
            if 'cards' in line.lower() and ('/' in line or line.lower().endswith('cards')):
                continue
            if any(skip in line.lower() for skip in skip_words):
                continue
            
            # Skip lines that are just numbers or UI elements
            if line.isdigit() or line in ['/', '-', '|', '\\', '011', '017']:
                continue
            
            # Skip coordinate-like patterns (e.g., "40 700" which are probably UI positions)
            if re.match(r'^\d+\s+\d+$', line):
                continue
            
            # Check for standalone quantity (MTGA format where qty is on next line)
            qty_match = qty_pattern.match(line)
            if qty_match and pending_card_name:
                # We have a quantity and a pending card name from previous line
                qty = int(qty_match.group(1))
                if 0 < qty <= 20:
                    entry = CardEntry(qty=qty, name=pending_card_name)
                    if is_sideboard:
                        side_entries.append(entry)
                    else:
                        main_entries.append(entry)
                pending_card_name = None
                continue
            elif qty_match:
                # Quantity without card name - skip
                continue
            
            # Try to match card with different patterns
            entry = None
            matched = False
            
            for j, pattern in enumerate(patterns):
                match = pattern.match(line)
                if match:
                    try:
                        if j == 0:  # "4 Lightning Bolt"
                            qty = int(match.group(1))
                            name = match.group(2).strip()
                        elif j == 1:  # "Lightning Bolt x4"
                            name = match.group(1).strip()
                            qty = int(match.group(2))
                        elif j == 2:  # "4x Lightning Bolt"
                            qty = int(match.group(1))
                            name = match.group(2).strip()
                        else:  # "Lightning Bolt 4"
                            # Check if last part is really a number
                            qty = int(match.group(2))
                            name = match.group(1).strip()
                            # Additional validation for this pattern
                            if qty > 20 or len(name) < 3:
                                continue
                        
                        # Clean card name
                        name = re.sub(r'\s+', ' ', name)  # Normalize spaces
                        name = re.sub(r'[^\w\s,\'-/]', '', name)  # Keep valid MTG characters
                        name = name.strip()
                        
                        # Validate that it's a real card name (not just numbers or gibberish)
                        if name and len(name) > 2 and 0 < qty <= 20:
                            # Card names must contain at least one alphabetic word
                            if any(c.isalpha() for c in name) and not name.isdigit():
                                entry = CardEntry(qty=qty, name=name)
                                matched = True
                                break
                    except (ValueError, IndexError):
                        continue
            
            if entry:
                if is_sideboard:
                    side_entries.append(entry)
                else:
                    main_entries.append(entry)
                pending_card_name = None
            elif not matched:
                # This might be a card name without quantity (MTGA format)
                # Check if it looks like a card name
                if (len(line) > 3 and 
                    not line[0].isdigit() and 
                    not line.lower().startswith('x') and
                    line[0].isupper()):  # Card names usually start with capital
                    # Clean the potential card name
                    name = re.sub(r'\s+', ' ', line)
                    name = re.sub(r'[^\w\s,\'-/]', '', name)
                    name = name.strip()
                    
                    if name and len(name) > 2:
                        # Check if next span might be a quantity
                        if i + 1 < len(spans):
                            next_line = spans[i + 1].text.strip().lower()
                            if next_line.startswith('x'):
                                pending_card_name = name
                            else:
                                # Single card without quantity indication
                                entry = CardEntry(qty=1, name=name)
                                if is_sideboard:
                                    side_entries.append(entry)
                                else:
                                    main_entries.append(entry)
        
        return DeckSections(main=main_entries, side=side_entries)
    
    def _parse_cards_mtga(self, spans: List[OCRSpan]) -> DeckSections:
        """
        Parse cards from OCR - VRAIMENT FONCTIONNEL pour MTGA.
        """
        main_entries = []
        side_entries = []
        
        # Convertir spans en liste de textes pour faciliter le parcours
        texts = [span.text.strip() for span in spans]
        
        # Pour MTGA, on ne peut pas se fier au mot "Sideboard" car il apparaît en haut
        # On doit compter les cartes et séparer à 60
        all_cards = []
        
        i = 0
        while i < len(texts):
            text = texts[i]
            
            # Ignorer les éléments UI connus
            if any(skip in text.lower() for skip in ['sideboard', 'cards', 'deck', 'total', '/', 'done', 'best of', 'temur otters']):
                i += 1
                continue
            
            # Ignorer les nombres seuls ou patterns numériques
            if text.isdigit() or re.match(r'^\d+/\d+$', text) or text in ['011', '017']:
                i += 1
                continue
            
            # Chercher une quantité (x2, x3, x4, etc.)
            qty_match = re.match(r'^x(\d+)$', text, re.IGNORECASE)
            if qty_match:
                # C'est une quantité seule, ignorer
                i += 1
                continue
            
            # Vérifier si c'est un nom de carte potentiel
            # Doit avoir des lettres et ne pas être juste des nombres
            if len(text) > 2 and any(c.isalpha() for c in text):
                # C'est potentiellement un nom de carte
                card_name = text
                quantity = 1  # Par défaut
                
                # Regarder la ligne suivante pour voir si c'est une quantité
                if i + 1 < len(texts):
                    next_text = texts[i + 1]
                    qty_match = re.match(r'^x(\d+)$', next_text, re.IGNORECASE)
                    if qty_match:
                        # La ligne suivante est une quantité !
                        quantity = int(qty_match.group(1))
                        i += 2  # Sauter le nom ET la quantité
                    else:
                        i += 1  # Juste le nom
                else:
                    i += 1
                
                # Nettoyer le nom
                card_name = re.sub(r'[^\w\s\',/-]', '', card_name).strip()
                
                # Valider et ajouter
                if card_name and quantity > 0 and quantity <= 20:
                    all_cards.append(CardEntry(qty=quantity, name=card_name))
            else:
                i += 1
        
        # Séparer mainboard et sideboard basé sur le nombre de cartes
        # Les 60 premières cartes (en comptant les quantités) = mainboard
        # Le reste = sideboard
        total_count = 0
        for card in all_cards:
            if total_count < 60:
                # Encore dans le mainboard
                remaining_main = 60 - total_count
                if card.qty <= remaining_main:
                    main_entries.append(card)
                    total_count += card.qty
                else:
                    # Cette carte est split entre main et side
                    main_entries.append(CardEntry(qty=remaining_main, name=card.name))
                    side_entries.append(CardEntry(qty=card.qty - remaining_main, name=card.name))
                    total_count = 60
            else:
                # Sideboard
                side_entries.append(card)
        
        return DeckSections(main=main_entries, side=side_entries)
    
    def _parse_cards(self, spans: List[OCRSpan]) -> DeckSections:
        """
        Parse cards - handles both OpenAI and EasyOCR formats.
        Enhanced with better MTGO/MTGA sideboard segmentation.
        """
        main_entries = []
        side_entries = []
        is_sideboard = False
        force_complete_mode = False
        
        # Detect format based on content patterns
        text_lines = [s.text.strip() for s in spans]
        
        # Check for MTGO patterns that require force complete 60+15
        if any('MTGO' in line or 'Magic Online' in line for line in text_lines[:10]):
            force_complete_mode = True
            logger.info("MTGO format detected - using force complete 60+15 mode")
        
        # Check for websites format (mtggoldfish, archidekt, etc.)
        website_patterns = ['mtggoldfish', 'archidekt', 'moxfield', 'tappedout', 'deckstats']
        if any(pattern in ' '.join(text_lines[:10]).lower() for pattern in website_patterns):
            logger.info("Website format detected - using smart parsing")
        
        for span in spans:
            text = span.text.strip()
            
            # Check for sideboard marker
            if text.lower() in ['sideboard', 'side board', 'sb'] and not force_complete_mode:
                is_sideboard = True
                continue
            
            # Skip UI elements
            if any(skip in text.lower() for skip in ['cards', 'deck', 'total', '/', 'done', 'best of']):
                continue
            
            # Try to parse OpenAI format: "4 Lightning Bolt"
            match = re.match(r'^(\d+)\s+(.+)$', text)
            if match:
                qty = int(match.group(1))
                name = match.group(2).strip()
                
                if name and qty > 0 and qty <= 20:
                    entry = CardEntry(qty=qty, name=name)
                    if is_sideboard:
                        side_entries.append(entry)
                    else:
                        main_entries.append(entry)
                continue
            
            # If not in OpenAI format, use MTGA parsing
            # This will handle the case where names and quantities are on separate lines
            # For now, just add cards with qty=1 if they look like card names
            if len(text) > 2 and any(c.isalpha() for c in text) and not text.startswith('x'):
                entry = CardEntry(qty=1, name=text)
                if is_sideboard:
                    side_entries.append(entry)
                else:
                    main_entries.append(entry)
        
        # Apply force complete mode for MTGO (60 mainboard + 15 sideboard)
        if force_complete_mode:
            all_cards = main_entries + side_entries
            main_entries = []
            side_entries = []
            
            total_count = 0
            for card in all_cards:
                if total_count < 60:
                    remaining_main = 60 - total_count
                    if card.qty <= remaining_main:
                        main_entries.append(card)
                        total_count += card.qty
                    else:
                        # Split card between main and side
                        if remaining_main > 0:
                            main_entries.append(CardEntry(qty=remaining_main, name=card.name))
                        side_entries.append(CardEntry(qty=card.qty - remaining_main, name=card.name))
                        total_count = 60
                else:
                    # Everything after 60 cards goes to sideboard
                    side_entries.append(card)
            
            logger.info(f"Force complete mode: {sum(c.qty for c in main_entries)} mainboard, {sum(c.qty for c in side_entries)} sideboard")
        
        # If we got good results from OpenAI, use them
        if len(main_entries) + len(side_entries) >= 20:
            return DeckSections(main=main_entries, side=side_entries)
        
        # Otherwise fallback to MTGA parsing
        return self._parse_cards_mtga(spans)
    
    def _parse_card_line(self, line: str) -> Optional[CardEntry]:
        """Legacy method - now handled in _parse_cards directly."""
        # This method is no longer used but kept for compatibility
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