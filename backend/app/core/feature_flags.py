"""
Feature flags for controlling application behavior.
Safe defaults for production, explicit overrides for testing.
"""

import os
from typing import Dict, Any

class FeatureFlags:
    """
    Centralized feature flag management.
    All flags default to safe/conservative values.
    """
    
    @staticmethod
    def use_vision_fallback() -> bool:
        """Check if OpenAI Vision API fallback is enabled."""
        return os.getenv("VISION_OCR_FALLBACK", "off").lower() == "on"
    
    @staticmethod
    def use_fuzzy_strict_mode() -> bool:
        """Check if strict fuzzy matching is enabled (tighter thresholds)."""
        return os.getenv("FUZZY_STRICT_MODE", "on").lower() == "on"
    
    @staticmethod
    def use_scryfall_online() -> bool:
        """Check if online Scryfall API is enabled (vs offline only)."""
        return os.getenv("SCRYFALL_ONLINE", "off").lower() == "on"
    
    @staticmethod
    def get_ocr_engine() -> str:
        """Get OCR engine to use."""
        engine = os.getenv("OCR_ENGINE", "easyocr").lower()
        if engine not in ["easyocr"]:  # Only EasyOCR allowed
            return "easyocr"
        return engine
    
    @staticmethod
    def get_ocr_languages() -> list[str]:
        """Get OCR languages to load."""
        langs = os.getenv("OCR_LANGUAGES", "en").lower()
        # Parse comma-separated list
        lang_list = [l.strip() for l in langs.split(",")]
        # Validate languages
        valid_langs = {"en", "fr", "de", "es", "it", "pt", "ja", "ko", "zh"}
        return [l for l in lang_list if l in valid_langs] or ["en"]
    
    @staticmethod
    def get_max_image_size() -> int:
        """Get maximum image dimension (for downscaling)."""
        return int(os.getenv("MAX_IMAGE_SIZE", "1920"))
    
    @staticmethod
    def get_ocr_confidence_threshold() -> float:
        """Get minimum OCR confidence threshold."""
        return float(os.getenv("OCR_MIN_CONF", "0.62"))
    
    @staticmethod
    def get_cache_ttl() -> int:
        """Get cache TTL in seconds."""
        return int(os.getenv("CACHE_TTL", "3600"))
    
    @staticmethod
    def use_deterministic_mode() -> bool:
        """Check if deterministic mode is enabled (for benchmarking)."""
        return os.getenv("DETERMINISTIC_MODE", "off").lower() == "on"
    
    @staticmethod
    def get_thread_count() -> int:
        """Get number of threads to use (1 for deterministic)."""
        if FeatureFlags.use_deterministic_mode():
            return 1
        return int(os.getenv("S2D_THREADS", "4"))
    
    @staticmethod
    def use_gpu() -> bool:
        """Check if GPU acceleration is enabled."""
        return os.getenv("USE_GPU", "auto").lower() in ["on", "auto"]
    
    @staticmethod
    def get_all_flags() -> Dict[str, Any]:
        """Get all feature flags as dict (for logging/debugging)."""
        return {
            "ocr_engine": FeatureFlags.get_ocr_engine(),
            "ocr_languages": FeatureFlags.get_ocr_languages(),
            "vision_fallback": FeatureFlags.use_vision_fallback(),
            "fuzzy_strict_mode": FeatureFlags.use_fuzzy_strict_mode(),
            "scryfall_online": FeatureFlags.use_scryfall_online(),
            "max_image_size": FeatureFlags.get_max_image_size(),
            "ocr_confidence": FeatureFlags.get_ocr_confidence_threshold(),
            "cache_ttl": FeatureFlags.get_cache_ttl(),
            "deterministic": FeatureFlags.use_deterministic_mode(),
            "threads": FeatureFlags.get_thread_count(),
            "gpu": FeatureFlags.use_gpu(),
        }
    
    @staticmethod
    def validate_flags():
        """Validate flag configuration and warn about issues."""
        import logging
        logger = logging.getLogger(__name__)
        
        flags = FeatureFlags.get_all_flags()
        
        # Warn if Vision fallback is enabled (project constraint)
        if flags["vision_fallback"]:
            logger.warning("⚠️ Vision OCR fallback is ON - this violates project constraints!")
        
        # Warn if using multiple languages (performance impact)
        if len(flags["ocr_languages"]) > 1:
            logger.warning(f"⚠️ Multiple OCR languages loaded: {flags['ocr_languages']} - performance impact!")
        
        # Info about deterministic mode
        if flags["deterministic"]:
            logger.info("🔒 Deterministic mode enabled - single-threaded execution")
        
        # Warn if Scryfall online in benchmark
        if flags["scryfall_online"] and flags["deterministic"]:
            logger.warning("⚠️ Scryfall online + deterministic mode - results may vary!")
        
        logger.info(f"Feature flags: {flags}")
        
        return flags