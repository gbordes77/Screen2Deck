"""
API endpoint tests for Screen2Deck.
"""

import pytest
from fastapi import status
from unittest.mock import patch, Mock
import json

class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test health endpoint returns OK."""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "healthy"}

class TestOCRUpload:
    """Test OCR upload endpoint."""
    
    def test_upload_valid_image(self, client, sample_image, mock_scryfall):
        """Test uploading a valid image."""
        with patch('app.main.process_ocr_task.delay') as mock_task:
            mock_task.return_value.id = "celery-task-123"
            
            response = client.post(
                "/api/ocr/upload",
                files={"file": ("test.png", sample_image, "image/png")}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "jobId" in data
            assert len(data["jobId"]) == 36  # UUID length
    
    def test_upload_invalid_file_type(self, client):
        """Test uploading non-image file."""
        response = client.post(
            "/api/ocr/upload",
            files={"file": ("test.txt", b"not an image", "text/plain")}
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unsupported content type" in response.json()["detail"]["message"]
    
    def test_upload_oversized_image(self, client, test_settings):
        """Test uploading oversized image."""
        test_settings.MAX_IMAGE_MB = 0.001  # 1KB limit
        large_image = b"x" * 2000  # 2KB
        
        response = client.post(
            "/api/ocr/upload",
            files={"file": ("large.png", large_image, "image/png")}
        )
        
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "Image too large" in response.json()["detail"]["message"]
    
    def test_rate_limiting(self, client, sample_image):
        """Test rate limiting on upload endpoint."""
        # First request should succeed
        response1 = client.post(
            "/api/ocr/upload",
            files={"file": ("test.png", sample_image, "image/png")}
        )
        assert response1.status_code == status.HTTP_200_OK
        
        # Immediate second request should be rate limited
        response2 = client.post(
            "/api/ocr/upload",
            files={"file": ("test.png", sample_image, "image/png")}
        )
        assert response2.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Too many requests" in response2.json()["detail"]["message"]

class TestJobStatus:
    """Test job status endpoint."""
    
    def test_get_job_status_completed(self, client, sample_deck_result):
        """Test getting status of completed job."""
        job_id = "test-job-123"
        
        with patch('app.tasks.get_job_status') as mock_status:
            mock_status.return_value = {
                "state": "completed",
                "progress": 100,
                "result": sample_deck_result
            }
            
            response = client.get(f"/api/ocr/status/{job_id}")
            assert response.status_code == status.HTTP_200_OK
            
            data = response.json()
            assert data["state"] == "completed"
            assert data["progress"] == 100
            assert data["result"]["jobId"] == job_id
    
    def test_get_job_status_processing(self, client):
        """Test getting status of processing job."""
        job_id = "test-job-456"
        
        with patch('app.tasks.get_job_status') as mock_status:
            mock_status.return_value = {
                "state": "processing",
                "progress": 50
            }
            
            response = client.get(f"/api/ocr/status/{job_id}")
            assert response.status_code == status.HTTP_200_OK
            
            data = response.json()
            assert data["state"] == "processing"
            assert data["progress"] == 50
    
    def test_get_job_status_not_found(self, client):
        """Test getting status of non-existent job."""
        job_id = "non-existent-job"
        
        with patch('app.tasks.get_job_status') as mock_status:
            mock_status.return_value = {"state": "not_found"}
            
            response = client.get(f"/api/ocr/status/{job_id}")
            assert response.status_code == status.HTTP_404_NOT_FOUND

class TestExportEndpoints:
    """Test export endpoints."""
    
    @pytest.mark.parametrize("format", ["mtga", "moxfield", "archidekt", "tappedout"])
    def test_export_format(self, client, format):
        """Test exporting deck to various formats."""
        deck_data = {
            "main": [
                {"qty": 4, "name": "Lightning Bolt", "scryfall_id": "abc123"}
            ],
            "side": []
        }
        
        response = client.post(
            f"/api/export/{format}",
            json=deck_data
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "text" in data
        assert "format" in data
        assert data["format"] == format

class TestAuthentication:
    """Test authentication and authorization."""
    
    def test_protected_endpoint_without_auth(self, client):
        """Test accessing protected endpoint without authentication."""
        # Assuming we add auth requirement to status endpoint
        with patch('app.main.require_permission') as mock_auth:
            mock_auth.side_effect = lambda perm: lambda: None
            
            response = client.get("/api/protected/resource")
            
            # Should return 401 without auth header
            if response.status_code == status.HTTP_404_NOT_FOUND:
                pytest.skip("Protected endpoint not implemented yet")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_protected_endpoint_with_valid_token(self, client, auth_headers):
        """Test accessing protected endpoint with valid JWT."""
        with patch('app.auth.verify_token') as mock_verify:
            mock_verify.return_value = Mock(permissions=["ocr:read"])
            
            response = client.get(
                "/api/protected/resource",
                headers=auth_headers
            )
            
            # Should allow access with valid token
            if response.status_code == status.HTTP_404_NOT_FOUND:
                pytest.skip("Protected endpoint not implemented yet")
            assert response.status_code != status.HTTP_401_UNAUTHORIZED

class TestCacheIntegration:
    """Test cache integration."""
    
    def test_cache_hit_on_duplicate_image(self, client, sample_image, mock_cache):
        """Test that duplicate images are served from cache."""
        mock_cache.get_ocr_result.return_value = {
            "jobId": "cached-job",
            "raw": {"spans": [], "mean_conf": 0.9}
        }
        
        with patch('app.services.ocr_service.cache_manager', mock_cache):
            response = client.post(
                "/api/ocr/upload",
                files={"file": ("test.png", sample_image, "image/png")}
            )
            
            assert response.status_code == status.HTTP_200_OK
            # Verify cache was checked
            assert mock_cache.get_ocr_result.called