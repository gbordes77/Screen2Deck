"""
Circuit breaker for Vision API fallback with automatic threshold adjustment.
Prevents cascading failures and controls costs.
"""

import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import statistics

from app.config import settings
from app.core.telemetry import logger
from app.core.metrics import vision_fallback_total, errors_total


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Blocking calls
    HALF_OPEN = "half_open"  # Testing recovery


class VisionFallbackCircuitBreaker:
    """
    Circuit breaker for Vision API fallback.
    Monitors fallback rate and automatically adjusts thresholds or disables fallback.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        fallback_rate_threshold: float = 0.15,  # 15% max fallback rate
        monitoring_window: int = 900  # 15 minutes
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            fallback_rate_threshold: Max acceptable fallback rate
            monitoring_window: Time window for rate monitoring (seconds)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.fallback_rate_threshold = fallback_rate_threshold
        self.monitoring_window = monitoring_window
        
        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.circuit_opened_at = None
        
        # Fallback rate tracking
        self.fallback_history = []  # List of (timestamp, used_fallback) tuples
        self.total_requests = 0
        self.fallback_requests = 0
        
        # Dynamic threshold adjustment
        self.current_confidence_threshold = settings.OCR_MIN_CONF
        self.current_min_lines = settings.OCR_MIN_LINES
        self.threshold_adjustments = []
    
    def record_request(self, used_fallback: bool) -> None:
        """
        Record an OCR request.
        
        Args:
            used_fallback: Whether Vision fallback was used
        """
        now = time.time()
        self.fallback_history.append((now, used_fallback))
        self.total_requests += 1
        
        if used_fallback:
            self.fallback_requests += 1
        
        # Clean old history
        cutoff = now - self.monitoring_window
        self.fallback_history = [(t, f) for t, f in self.fallback_history if t > cutoff]
    
    def get_fallback_rate(self) -> float:
        """
        Calculate current fallback rate over monitoring window.
        
        Returns:
            Fallback rate (0.0 to 1.0)
        """
        if not self.fallback_history:
            return 0.0
        
        recent_fallbacks = sum(1 for _, used in self.fallback_history if used)
        return recent_fallbacks / len(self.fallback_history)
    
    def should_use_fallback(self, confidence: float, lines: int) -> bool:
        """
        Determine if Vision fallback should be used.
        
        Args:
            confidence: OCR confidence score
            lines: Number of lines detected
            
        Returns:
            True if fallback should be used
        """
        # Check circuit state
        if self.state == CircuitState.OPEN:
            # Check if we should try recovery
            if self.circuit_opened_at and \
               time.time() - self.circuit_opened_at > self.recovery_timeout:
                logger.info("Circuit breaker entering HALF_OPEN state")
                self.state = CircuitState.HALF_OPEN
            else:
                logger.warning("Circuit breaker OPEN - Vision fallback disabled")
                return False
        
        # Check fallback rate
        current_rate = self.get_fallback_rate()
        if current_rate > self.fallback_rate_threshold:
            logger.warning(
                f"Fallback rate {current_rate:.2%} exceeds threshold {self.fallback_rate_threshold:.2%}"
            )
            self._adjust_thresholds()
            return False
        
        # Apply dynamic thresholds
        if confidence < self.current_confidence_threshold:
            return True
        
        if lines < self.current_min_lines:
            return True
        
        return False
    
    def record_success(self) -> None:
        """Record successful Vision API call."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker closing after successful call")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
        
        vision_fallback_total.labels(reason='success').inc()
    
    def record_failure(self, error: Exception) -> None:
        """
        Record Vision API failure.
        
        Args:
            error: The exception that occurred
        """
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        errors_total.labels(error_type='vision_api', component='fallback').inc()
        vision_fallback_total.labels(reason='error').inc()
        
        logger.error(f"Vision API failure {self.failure_count}/{self.failure_threshold}: {error}")
        
        # Open circuit if threshold exceeded
        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                logger.warning("Opening circuit breaker due to failures")
                self.state = CircuitState.OPEN
                self.circuit_opened_at = time.time()
    
    def _adjust_thresholds(self) -> None:
        """
        Automatically adjust confidence thresholds to reduce fallback rate.
        """
        # Increase confidence threshold by 5%
        old_threshold = self.current_confidence_threshold
        self.current_confidence_threshold = min(0.95, self.current_confidence_threshold + 0.05)
        
        # Increase min lines by 2
        old_lines = self.current_min_lines
        self.current_min_lines = min(20, self.current_min_lines + 2)
        
        self.threshold_adjustments.append({
            'timestamp': datetime.utcnow(),
            'old_confidence': old_threshold,
            'new_confidence': self.current_confidence_threshold,
            'old_lines': old_lines,
            'new_lines': self.current_min_lines,
            'reason': 'high_fallback_rate'
        })
        
        logger.warning(
            f"Adjusted thresholds - Confidence: {old_threshold:.2f} → {self.current_confidence_threshold:.2f}, "
            f"Min lines: {old_lines} → {self.current_min_lines}"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get circuit breaker status.
        
        Returns:
            Status dictionary
        """
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'fallback_rate': self.get_fallback_rate(),
            'total_requests': self.total_requests,
            'fallback_requests': self.fallback_requests,
            'current_thresholds': {
                'confidence': self.current_confidence_threshold,
                'min_lines': self.current_min_lines
            },
            'adjustments': len(self.threshold_adjustments),
            'last_adjustment': self.threshold_adjustments[-1] if self.threshold_adjustments else None
        }
    
    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.circuit_opened_at = None
        self.current_confidence_threshold = settings.OCR_MIN_CONF
        self.current_min_lines = settings.OCR_MIN_LINES
        logger.info("Circuit breaker reset")


class ResolutionBasedThresholds:
    """
    Adjust Vision fallback thresholds based on image resolution.
    """
    
    # Resolution bands with confidence thresholds
    RESOLUTION_BANDS = {
        'low': {
            'max_pixels': 921600,      # 720p (1280x720)
            'confidence_threshold': 0.55,
            'min_lines': 8
        },
        'hd': {
            'max_pixels': 2073600,      # 1080p (1920x1080)
            'confidence_threshold': 0.62,
            'min_lines': 10
        },
        'fullhd': {
            'max_pixels': 3686400,      # 1440p (2560x1440)
            'confidence_threshold': 0.68,
            'min_lines': 12
        },
        '4k': {
            'max_pixels': float('inf'),  # 4K and above
            'confidence_threshold': 0.72,
            'min_lines': 15
        }
    }
    
    @classmethod
    def get_thresholds(cls, width: int, height: int) -> Dict[str, Any]:
        """
        Get appropriate thresholds based on image resolution.
        
        Args:
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            Dictionary with confidence_threshold and min_lines
        """
        pixels = width * height
        
        for band_name, band_config in cls.RESOLUTION_BANDS.items():
            if pixels <= band_config['max_pixels']:
                logger.debug(f"Using {band_name} resolution thresholds for {width}x{height}")
                return {
                    'confidence_threshold': band_config['confidence_threshold'],
                    'min_lines': band_config['min_lines'],
                    'resolution_band': band_name
                }
        
        # Default to 4K settings
        return cls.RESOLUTION_BANDS['4k']


# Global circuit breaker instance
vision_circuit_breaker = VisionFallbackCircuitBreaker()