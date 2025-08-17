"""
Pytest configuration and fixtures for Screen2Deck tests.
"""

import pytest
import asyncio
from typing import Generator
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import numpy as np
import cv2

# Import app and dependencies
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.config import Settings, get_settings
from app.cache_manager import CacheManager

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_settings():
    """Override settings for testing."""
    test_settings = Settings()
    test_settings.USE_REDIS = False  # Use memory cache in tests
    test_settings.ALWAYS_VERIFY_SCRYFALL = False  # Disable external calls
    test_settings.ENABLE_VISION_FALLBACK = False
    return test_settings

@pytest.fixture
def mock_settings(test_settings):
    """Mock get_settings to return test settings."""
    with patch('app.config.get_settings', return_value=test_settings):
        yield test_settings

@pytest.fixture
def client(mock_settings) -> Generator:
    """Create test client."""
    with TestClient(app) as c:
        yield c

@pytest.fixture
def mock_cache():
    """Mock cache manager."""
    cache = Mock(spec=CacheManager)
    cache.get.return_value = None
    cache.set.return_value = True
    cache.delete.return_value = True
    cache.exists.return_value = False
    return cache

@pytest.fixture
def sample_image():
    """Create a sample test image."""
    # Create a simple white image with text-like patterns
    img = np.ones((600, 400, 3), dtype=np.uint8) * 255
    
    # Add some text-like black rectangles
    cv2.rectangle(img, (50, 50), (350, 100), (0, 0, 0), -1)
    cv2.rectangle(img, (50, 120), (350, 170), (0, 0, 0), -1)
    cv2.rectangle(img, (50, 190), (350, 240), (0, 0, 0), -1)
    
    # Encode as PNG
    _, buffer = cv2.imencode('.png', img)
    return buffer.tobytes()

@pytest.fixture
def sample_ocr_result():
    """Sample OCR result for testing."""
    return {
        "spans": [
            {"text": "4 Lightning Bolt", "conf": 0.95},
            {"text": "4 Counterspell", "conf": 0.92},
            {"text": "2 Teferi, Hero of Dominaria", "conf": 0.88},
            {"text": "Sideboard", "conf": 0.90},
            {"text": "3 Negate", "conf": 0.91}
        ],
        "mean_conf": 0.91
    }

@pytest.fixture
def sample_deck_result():
    """Sample deck result for testing."""
    return {
        "jobId": "test-job-123",
        "raw": {
            "spans": [
                {"text": "4 Lightning Bolt", "conf": 0.95},
                {"text": "4 Counterspell", "conf": 0.92}
            ],
            "mean_conf": 0.93
        },
        "parsed": {
            "main": [
                {"qty": 4, "name": "Lightning Bolt", "candidates": []},
                {"qty": 4, "name": "Counterspell", "candidates": []}
            ],
            "side": []
        },
        "normalized": {
            "main": [
                {"qty": 4, "name": "Lightning Bolt", "scryfall_id": "abc123"},
                {"qty": 4, "name": "Counterspell", "scryfall_id": "def456"}
            ],
            "side": []
        },
        "timings_ms": {
            "preprocess": 150,
            "ocr": 850,
            "scryfall": 200,
            "total": 1200
        },
        "traceId": "test-trace-123"
    }

@pytest.fixture
def auth_headers():
    """Generate auth headers with test JWT token."""
    from app.auth import create_access_token
    token = create_access_token(
        data={"job_id": "test-job", "permissions": ["ocr:read", "ocr:write"]}
    )
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def mock_scryfall():
    """Mock Scryfall client."""
    with patch('app.matching.scryfall_client.SCRYFALL') as mock:
        mock.all_names.return_value = [
            "Lightning Bolt",
            "Counterspell",
            "Teferi, Hero of Dominaria",
            "Negate"
        ]
        mock.resolve.return_value = {
            "name": "Lightning Bolt",
            "id": "abc123",
            "candidates": []
        }
        mock.lookup_by_name.return_value = [
            {"id": "abc123", "name": "Lightning Bolt"}
        ]
        yield mock

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch('redis.from_url') as mock:
        redis_mock = Mock()
        redis_mock.get.return_value = None
        redis_mock.set.return_value = True
        redis_mock.setex.return_value = True
        redis_mock.delete.return_value = 1
        redis_mock.exists.return_value = 0
        redis_mock.ping.return_value = True
        mock.return_value = redis_mock
        yield redis_mock