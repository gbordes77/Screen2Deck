"""
Custom exceptions and error handling for Screen2Deck.
Provides comprehensive error handling with proper error codes and messages.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from .telemetry import logger

class Screen2DeckException(Exception):
    """Base exception for Screen2Deck application."""
    
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class ImageProcessingError(Screen2DeckException):
    """Error during image processing."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="IMAGE_PROCESSING_ERROR",
            status_code=400,
            details=details
        )

class OCRProcessingError(Screen2DeckException):
    """Error during OCR processing."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            code="OCR_PROCESSING_ERROR",
            status_code=500,
            details=details
        )

class ValidationError(Screen2DeckException):
    """Data validation error."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details
        )

class AuthenticationError(Screen2DeckException):
    """Authentication failed."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401
        )

class AuthorizationError(Screen2DeckException):
    """Authorization failed."""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403
        )

class RateLimitError(Screen2DeckException):
    """Rate limit exceeded."""
    
    def __init__(self, message: str = "Too many requests", retry_after: Optional[int] = None):
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details
        )

class JobNotFoundError(Screen2DeckException):
    """Job not found."""
    
    def __init__(self, job_id: str):
        super().__init__(
            message=f"Job {job_id} not found",
            code="JOB_NOT_FOUND",
            status_code=404,
            details={"job_id": job_id}
        )

class ExternalServiceError(Screen2DeckException):
    """External service error (Scryfall, Vision API, etc.)."""
    
    def __init__(self, service: str, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=f"{service} error: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=503,
            details={"service": service, **(details or {})}
        )

class CacheError(Screen2DeckException):
    """Cache operation error."""
    
    def __init__(self, message: str, operation: str):
        super().__init__(
            message=message,
            code="CACHE_ERROR",
            status_code=500,
            details={"operation": operation}
        )

# Global error handlers

async def screen2deck_exception_handler(request: Request, exc: Screen2DeckException):
    """Handle Screen2Deck custom exceptions."""
    logger.error(f"Screen2Deck error: {exc.code} - {exc.message}", extra={
        "code": exc.code,
        "details": exc.details,
        "path": request.url.path
    })
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle FastAPI HTTP exceptions."""
    logger.warning(f"HTTP error: {exc.status_code} - {exc.detail}", extra={
        "status_code": exc.status_code,
        "path": request.url.path
    })
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail
            }
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    errors = exc.errors()
    logger.warning(f"Validation error: {errors}", extra={
        "path": request.url.path,
        "errors": errors
    })
    
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"validation_errors": errors}
            }
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"Unexpected error: {str(exc)}", extra={
        "path": request.url.path,
        "exception_type": type(exc).__name__
    })
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred"
            }
        }
    )

def register_error_handlers(app):
    """Register all error handlers with the FastAPI app."""
    app.add_exception_handler(Screen2DeckException, screen2deck_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

# Context manager for error handling
class ErrorHandler:
    """Context manager for consistent error handling."""
    
    def __init__(self, operation: str, trace_id: Optional[str] = None):
        self.operation = operation
        self.trace_id = trace_id
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            logger.error(
                f"Error in {self.operation}: {str(exc_val)}",
                extra={
                    "operation": self.operation,
                    "trace_id": self.trace_id,
                    "exception_type": exc_type.__name__ if exc_type else None
                }
            )
            
            # Re-raise as appropriate Screen2Deck exception
            if isinstance(exc_val, Screen2DeckException):
                raise
            elif isinstance(exc_val, ValueError):
                raise ValidationError(str(exc_val))
            elif isinstance(exc_val, KeyError):
                raise ValidationError(f"Missing required field: {str(exc_val)}")
            elif isinstance(exc_val, ConnectionError):
                raise ExternalServiceError("Connection", str(exc_val))
            else:
                # Log the full traceback for unexpected errors
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise Screen2DeckException(
                    message="An error occurred during processing",
                    code="PROCESSING_ERROR",
                    details={"operation": self.operation}
                )
        return False