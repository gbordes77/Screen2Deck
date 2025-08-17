"""
Input validation and sanitization for Screen2Deck API.
Provides comprehensive validation for file uploads and user inputs.
"""

import hashlib
import io
import magic
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from fastapi import HTTPException, UploadFile, status

from ..telemetry import logger
from ..error_taxonomy import BAD_IMAGE, VALIDATION_ERROR

# Allowed image MIME types
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg", 
    "image/png",
    "image/webp",
    "image/gif",  # Static GIFs only
    "image/bmp",
    "image/tiff",
}

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", 
    ".gif", ".bmp", ".tiff", ".tif"
}

# Maximum image dimensions
MAX_IMAGE_WIDTH = 4096
MAX_IMAGE_HEIGHT = 4096
MIN_IMAGE_WIDTH = 100
MIN_IMAGE_HEIGHT = 100

# File size limits
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MIN_FILE_SIZE = 1024  # 1KB

class ImageValidator:
    """
    Comprehensive image validation and sanitization.
    """
    
    def __init__(self, max_size_mb: int = 10):
        """
        Initialize validator.
        
        Args:
            max_size_mb: Maximum file size in megabytes
        """
        self.max_size = max_size_mb * 1024 * 1024
        self.mime = magic.Magic(mime=True)
        
    async def validate_upload(
        self, 
        file: UploadFile,
        calculate_hash: bool = True
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Validate and sanitize uploaded image.
        
        Args:
            file: Uploaded file object
            calculate_hash: Whether to calculate SHA256 hash
            
        Returns:
            Tuple of (sanitized image bytes, metadata dict)
            
        Raises:
            HTTPException: If validation fails
        """
        metadata = {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": 0,
            "hash": None,
            "dimensions": None,
            "format": None
        }
        
        # Validate filename
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": BAD_IMAGE, "message": "Filename is required"}
            )
        
        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": BAD_IMAGE, 
                    "message": f"File type {file_ext} not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
                }
            )
        
        # Read file content
        content = await file.read()
        metadata["size"] = len(content)
        
        # Validate file size
        if len(content) > self.max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "code": BAD_IMAGE,
                    "message": f"File too large. Maximum size: {self.max_size // 1024 // 1024}MB"
                }
            )
        
        if len(content) < MIN_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": BAD_IMAGE, "message": "File too small"}
            )
        
        # Validate MIME type using magic bytes
        detected_mime = self.mime.from_buffer(content)
        if detected_mime not in ALLOWED_MIME_TYPES:
            logger.warning(f"Invalid MIME type detected: {detected_mime} for file {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": BAD_IMAGE,
                    "message": f"Invalid file type detected: {detected_mime}"
                }
            )
        
        metadata["format"] = detected_mime
        
        # Calculate hash for idempotency
        if calculate_hash:
            metadata["hash"] = hashlib.sha256(content).hexdigest()
        
        # Validate and sanitize image
        try:
            # Decode image
            img_array = np.frombuffer(content, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if img is None:
                raise ValueError("Cannot decode image")
            
            height, width = img.shape[:2]
            metadata["dimensions"] = {"width": width, "height": height}
            
            # Validate dimensions
            if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": BAD_IMAGE,
                        "message": f"Image too large: {width}x{height}. Maximum: {MAX_IMAGE_WIDTH}x{MAX_IMAGE_HEIGHT}"
                    }
                )
            
            if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": BAD_IMAGE,
                        "message": f"Image too small: {width}x{height}. Minimum: {MIN_IMAGE_WIDTH}x{MIN_IMAGE_HEIGHT}"
                    }
                )
            
            # Re-encode image to remove any malicious data
            # This strips EXIF data and any embedded scripts
            success, buffer = cv2.imencode('.png', img)
            if not success:
                raise ValueError("Failed to re-encode image")
            
            sanitized_content = buffer.tobytes()
            
            logger.info(
                f"Validated image: {file.filename}, "
                f"size: {len(content)} bytes, "
                f"dimensions: {width}x{height}, "
                f"hash: {metadata['hash'][:8]}..."
            )
            
            return sanitized_content, metadata
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Image validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": BAD_IMAGE, "message": "Invalid or corrupted image file"}
            )
    
    def validate_image_data(self, img: np.ndarray) -> bool:
        """
        Validate decoded image data.
        
        Args:
            img: OpenCV image array
            
        Returns:
            True if valid, False otherwise
        """
        if img is None:
            return False
        
        # Check if image is not empty
        if img.size == 0:
            return False
        
        # Check dimensions
        height, width = img.shape[:2]
        if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
            return False
        if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
            return False
        
        # Check if image has valid content (not all black/white)
        mean_val = np.mean(img)
        if mean_val < 1 or mean_val > 254:
            logger.warning(f"Image appears to be blank: mean value = {mean_val}")
            return False
        
        return True


class TextValidator:
    """
    Validate and sanitize text inputs.
    """
    
    @staticmethod
    def sanitize_card_name(name: str) -> str:
        """
        Sanitize card name input.
        
        Args:
            name: Raw card name
            
        Returns:
            Sanitized card name
        """
        if not name:
            return ""
        
        # Remove control characters
        name = "".join(ch for ch in name if ch.isprintable() or ch.isspace())
        
        # Normalize whitespace
        name = " ".join(name.split())
        
        # Limit length
        max_length = 200
        if len(name) > max_length:
            name = name[:max_length]
        
        # Remove potential SQL injection attempts
        dangerous_patterns = [
            "--", "/*", "*/", "xp_", "sp_", 
            "exec", "execute", "select", "insert", 
            "update", "delete", "drop", "create"
        ]
        
        name_lower = name.lower()
        for pattern in dangerous_patterns:
            if pattern in name_lower:
                logger.warning(f"Potential SQL injection attempt in card name: {name}")
                name = name.replace(pattern, "")
        
        return name.strip()
    
    @staticmethod
    def validate_export_format(format: str) -> bool:
        """
        Validate export format.
        
        Args:
            format: Export format string
            
        Returns:
            True if valid, False otherwise
        """
        allowed_formats = {"mtga", "moxfield", "archidekt", "tappedout", "json"}
        return format.lower() in allowed_formats
    
    @staticmethod
    def validate_job_id(job_id: str) -> bool:
        """
        Validate job ID format.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if valid UUID, False otherwise
        """
        import uuid
        try:
            uuid.UUID(job_id)
            return True
        except ValueError:
            return False


class RequestValidator:
    """
    Validate API requests.
    """
    
    @staticmethod
    def validate_pagination(limit: int, offset: int) -> Tuple[int, int]:
        """
        Validate and sanitize pagination parameters.
        
        Args:
            limit: Number of items to return
            offset: Starting position
            
        Returns:
            Tuple of (sanitized limit, sanitized offset)
        """
        # Sanitize limit
        if limit < 1:
            limit = 10
        elif limit > 100:
            limit = 100
        
        # Sanitize offset
        if offset < 0:
            offset = 0
        elif offset > 10000:
            offset = 10000
        
        return limit, offset
    
    @staticmethod
    def validate_headers(headers: dict) -> bool:
        """
        Validate request headers for security.
        
        Args:
            headers: Request headers dict
            
        Returns:
            True if valid, False otherwise
        """
        # Check for suspicious headers
        suspicious_headers = [
            "x-forwarded-host",  # Can be used for host header injection
            "x-original-url",    # Can bypass access controls
            "x-rewrite-url",      # Can bypass access controls
        ]
        
        for header in suspicious_headers:
            if header in headers:
                logger.warning(f"Suspicious header detected: {header}")
                return False
        
        # Check user agent
        user_agent = headers.get("user-agent", "").lower()
        blocked_agents = [
            "sqlmap",  # SQL injection tool
            "nikto",   # Web scanner
            "nessus",  # Vulnerability scanner
            "metasploit",  # Exploitation framework
        ]
        
        for agent in blocked_agents:
            if agent in user_agent:
                logger.warning(f"Blocked user agent detected: {user_agent}")
                return False
        
        return True


# Global validator instances
image_validator = ImageValidator()
text_validator = TextValidator()
request_validator = RequestValidator()