"""
Resilience patterns implementation.
Provides circuit breakers, retries, and timeouts.
"""

from typing import Callable, Any, Optional, TypeVar, Union
from functools import wraps
import asyncio
import time
from datetime import datetime, timedelta
from enum import Enum
import random
from collections import deque

from ..telemetry import logger

T = TypeVar('T')

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    """
    Circuit breaker implementation.
    Prevents cascading failures by stopping calls to failing services.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type to catch
            success_threshold: Successes needed to close circuit
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_attempt_time: Optional[datetime] = None
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker {self.name} entering HALF_OPEN state")
            else:
                raise Exception(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    async def call_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute async function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker {self.name} entering HALF_OPEN state")
            else:
                raise Exception(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        if not self.last_failure_time:
            return False
        
        return (datetime.utcnow() - self.last_failure_time).seconds >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.successes += 1
            if self.successes >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failures = 0
                self.successes = 0
                logger.info(f"Circuit breaker {self.name} closed")
        else:
            self.failures = 0
    
    def _on_failure(self):
        """Handle failed call."""
        self.failures += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.successes = 0
            logger.warning(f"Circuit breaker {self.name} reopened")
        elif self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker {self.name} opened after {self.failures} failures")
    
    def reset(self):
        """Manually reset circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure_time = None
    
    def get_state(self) -> dict:
        """Get circuit breaker state."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.failures,
            "successes": self.successes,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None
        }

def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception
):
    """Decorator for circuit breaker protection."""
    breaker = CircuitBreaker(name, failure_threshold, recovery_timeout, expected_exception)
    
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await breaker.call_async(func, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return breaker.call(func, *args, **kwargs)
            return sync_wrapper
    
    return decorator

class RetryStrategy:
    """Retry strategy with exponential backoff."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize retry strategy.
        
        Args:
            max_attempts: Maximum retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
            jitter: Add random jitter to delays
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for attempt number."""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        
        if self.jitter:
            # Add random jitter (0-25% of delay)
            delay *= (1 + random.random() * 0.25)
        
        return delay

def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retry with exponential backoff.
    
    Args:
        max_attempts: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exceptions: Exceptions to retry on
    """
    strategy = RetryStrategy(max_attempts, base_delay, max_delay)
    
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(strategy.max_attempts):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < strategy.max_attempts - 1:
                            delay = strategy.calculate_delay(attempt)
                            logger.warning(
                                f"Retry {attempt + 1}/{strategy.max_attempts} "
                                f"for {func.__name__} after {delay:.2f}s"
                            )
                            await asyncio.sleep(delay)
                
                raise last_exception
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(strategy.max_attempts):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < strategy.max_attempts - 1:
                            delay = strategy.calculate_delay(attempt)
                            logger.warning(
                                f"Retry {attempt + 1}/{strategy.max_attempts} "
                                f"for {func.__name__} after {delay:.2f}s"
                            )
                            time.sleep(delay)
                
                raise last_exception
            return sync_wrapper
    
    return decorator

class Bulkhead:
    """
    Bulkhead pattern implementation.
    Isolates resources to prevent total system failure.
    """
    
    def __init__(self, name: str, max_concurrent: int = 10, max_queue: int = 100):
        """
        Initialize bulkhead.
        
        Args:
            name: Bulkhead name
            max_concurrent: Maximum concurrent executions
            max_queue: Maximum queue size
        """
        self.name = name
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.queue_size = 0
        self.active = 0
    
    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with bulkhead protection."""
        if self.queue_size >= self.max_queue:
            raise Exception(f"Bulkhead {self.name} queue full")
        
        self.queue_size += 1
        try:
            async with self.semaphore:
                self.queue_size -= 1
                self.active += 1
                try:
                    return await func(*args, **kwargs)
                finally:
                    self.active -= 1
        except:
            self.queue_size -= 1
            raise
    
    def get_state(self) -> dict:
        """Get bulkhead state."""
        return {
            "name": self.name,
            "active": self.active,
            "queued": self.queue_size,
            "max_concurrent": self.max_concurrent,
            "max_queue": self.max_queue
        }

# Global circuit breakers
scryfall_breaker = CircuitBreaker(
    "scryfall",
    failure_threshold=5,
    recovery_timeout=30,
    expected_exception=ConnectionError
)

vision_api_breaker = CircuitBreaker(
    "vision_api",
    failure_threshold=3,
    recovery_timeout=60,
    expected_exception=Exception
)

# Global bulkheads
ocr_bulkhead = Bulkhead("ocr", max_concurrent=5, max_queue=50)
export_bulkhead = Bulkhead("export", max_concurrent=10, max_queue=100)