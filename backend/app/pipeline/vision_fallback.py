"""
OpenAI Vision API fallback for OCR with configurable thresholds and metrics.
"""

import base64
import time
from typing import Dict, Any, Optional
import cv2
import numpy as np
from openai import OpenAI
import json

from ..core.config import settings
from ..telemetry import logger, telemetry
from ..routers.metrics import record_ocr_duration, record_error

class VisionFallback:
    """
    OpenAI Vision API fallback with thresholds and metrics.
    """
    
    def __init__(
        self,
        confidence_threshold: float = 0.85,
        min_cards_threshold: int = 10,
        max_retries: int = 2
    ):
        """
        Initialize Vision fallback.
        
        Args:
            confidence_threshold: Minimum confidence to skip fallback
            min_cards_threshold: Minimum cards detected to skip fallback
            max_retries: Maximum retry attempts
        """
        self.confidence_threshold = confidence_threshold
        self.min_cards_threshold = min_cards_threshold
        self.max_retries = max_retries
        self.client = None
        
        if settings.OPENAI_API_KEY:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("Vision API fallback initialized")
        else:
            logger.warning("Vision API key not configured")
    
    def should_use_fallback(
        self,
        ocr_result: Dict[str, Any],
        confidence: float,
        card_count: int
    ) -> bool:
        """
        Determine if Vision fallback should be used.
        
        Args:
            ocr_result: Primary OCR result
            confidence: OCR confidence score
            card_count: Number of cards detected
            
        Returns:
            True if fallback should be used
        """
        if not self.client:
            return False
        
        if not settings.ENABLE_VISION_FALLBACK:
            return False
        
        # Check thresholds
        use_fallback = (
            confidence < self.confidence_threshold or
            card_count < self.min_cards_threshold
        )
        
        if use_fallback:
            logger.info(
                f"Using Vision fallback: conf={confidence:.2f} "
                f"(threshold={self.confidence_threshold}), "
                f"cards={card_count} (threshold={self.min_cards_threshold})"
            )
        
        return use_fallback
    
    async def process_with_vision(
        self,
        image: np.ndarray,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process image with OpenAI Vision API.
        
        Args:
            image: OpenCV image array
            prompt: Custom prompt for Vision API
            
        Returns:
            OCR result dictionary
        """
        if not self.client:
            raise ValueError("Vision API not configured")
        
        with telemetry.span("vision_api_fallback") as span:
            t0 = time.time()
            
            # Encode image to base64
            success, buffer = cv2.imencode('.jpg', image)
            if not success:
                raise ValueError("Failed to encode image")
            
            base64_image = base64.b64encode(buffer).decode('utf-8')
            
            # Default prompt for MTG cards
            if not prompt:
                prompt = """
                Extract all Magic: The Gathering cards from this deck list image.
                Return the result as a JSON object with this structure:
                {
                    "main": [{"qty": number, "name": "card name"}, ...],
                    "side": [{"qty": number, "name": "card name"}, ...],
                    "confidence": 0.0-1.0
                }
                
                Rules:
                - Mainboard cards come before "Sideboard" text
                - Sideboard cards come after "Sideboard" text
                - Each card has quantity and name
                - Be very precise with card names
                - Return confidence score for overall accuracy
                """
            
            # Call Vision API with retries
            for attempt in range(self.max_retries):
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-4-vision-preview",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{base64_image}",
                                            "detail": "high"
                                        }
                                    }
                                ]
                            }
                        ],
                        max_tokens=1000,
                        temperature=0.1
                    )
                    
                    # Parse response
                    content = response.choices[0].message.content
                    
                    # Try to parse as JSON
                    try:
                        result = json.loads(content)
                    except json.JSONDecodeError:
                        # Fallback to text parsing
                        result = self._parse_text_response(content)
                    
                    # Convert to OCR format
                    ocr_result = self._convert_to_ocr_format(result)
                    
                    # Record metrics
                    duration = time.time() - t0
                    record_ocr_duration(duration)
                    span.set_attribute("vision_api_success", True)
                    span.set_attribute("vision_api_duration", duration)
                    span.set_attribute("vision_api_confidence", result.get("confidence", 0.9))
                    
                    logger.info(f"Vision API processed in {duration:.2f}s")
                    
                    return ocr_result
                    
                except Exception as e:
                    logger.warning(f"Vision API attempt {attempt + 1} failed: {e}")
                    if attempt == self.max_retries - 1:
                        record_error("vision_api_error")
                        span.set_attribute("vision_api_success", False)
                        raise
                    time.sleep(2 ** attempt)  # Exponential backoff
    
    def _parse_text_response(self, text: str) -> Dict[str, Any]:
        """
        Parse text response from Vision API.
        
        Args:
            text: Text response from API
            
        Returns:
            Parsed deck structure
        """
        lines = text.strip().split('\n')
        main = []
        side = []
        current_section = main
        
        for line in lines:
            line = line.strip()
            
            # Check for sideboard marker
            if 'sideboard' in line.lower():
                current_section = side
                continue
            
            # Parse card line
            import re
            match = re.match(r'^(\d+)x?\s+(.+)$', line, re.IGNORECASE)
            if match:
                qty = int(match.group(1))
                name = match.group(2).strip()
                current_section.append({"qty": qty, "name": name})
        
        return {
            "main": main,
            "side": side,
            "confidence": 0.85  # Default confidence for text parsing
        }
    
    def _convert_to_ocr_format(self, vision_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Vision API result to OCR format.
        
        Args:
            vision_result: Result from Vision API
            
        Returns:
            OCR-compatible result dictionary
        """
        spans = []
        
        # Convert main deck
        for card in vision_result.get("main", []):
            text = f"{card['qty']} {card['name']}"
            spans.append({
                "text": text,
                "conf": vision_result.get("confidence", 0.9)
            })
        
        # Add sideboard marker
        if vision_result.get("side"):
            spans.append({
                "text": "Sideboard",
                "conf": 1.0
            })
            
            # Convert sideboard
            for card in vision_result.get("side", []):
                text = f"{card['qty']} {card['name']}"
                spans.append({
                    "text": text,
                    "conf": vision_result.get("confidence", 0.9)
                })
        
        return {
            "spans": spans,
            "mean_conf": vision_result.get("confidence", 0.9),
            "fallback_used": True,
            "method": "vision_api"
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get Vision API usage metrics.
        
        Returns:
            Metrics dictionary
        """
        return {
            "enabled": bool(self.client),
            "confidence_threshold": self.confidence_threshold,
            "min_cards_threshold": self.min_cards_threshold,
            "max_retries": self.max_retries
        }


# Global Vision fallback instance
vision_fallback = VisionFallback(
    confidence_threshold=settings.OCR_MIN_CONF,
    min_cards_threshold=settings.OCR_MIN_LINES
)