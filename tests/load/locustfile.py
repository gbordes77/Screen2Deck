"""
Load testing with Locust.
Tests API performance under various load conditions.
"""

from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser
import random
import base64
import io
from PIL import Image
import json
import time

# Sample image generation
def generate_test_image():
    """Generate a test image for OCR."""
    img = Image.new('RGB', (800, 600), color='white')
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio.read()

class Screen2DeckUser(FastHttpUser):
    """Load test user for Screen2Deck API."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Initialize user session."""
        # Generate test image once
        self.test_image = generate_test_image()
        self.job_ids = []
        
        # Get authentication token (if needed)
        # response = self.client.post("/api/auth/login", json={
        #     "username": "test",
        #     "password": "test"
        # })
        # self.token = response.json().get("access_token")
        # self.client.headers.update({"Authorization": f"Bearer {self.token}"})
    
    @task(10)
    def upload_image(self):
        """Test image upload endpoint."""
        with self.client.post(
            "/api/ocr/upload",
            files={"file": ("test.png", self.test_image, "image/png")},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                job_id = response.json().get("jobId")
                if job_id:
                    self.job_ids.append(job_id)
                    response.success()
                else:
                    response.failure("No job ID returned")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Got status code {response.status_code}")
    
    @task(20)
    def check_job_status(self):
        """Test job status endpoint."""
        if not self.job_ids:
            return
        
        job_id = random.choice(self.job_ids)
        with self.client.get(
            f"/api/ocr/status/{job_id}",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("state") == "completed":
                    # Remove completed jobs
                    self.job_ids = [j for j in self.job_ids if j != job_id]
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")
    
    @task(5)
    def export_deck(self):
        """Test export endpoint."""
        deck_data = {
            "main": [
                {"qty": 4, "name": "Lightning Bolt", "scryfall_id": "test"},
                {"qty": 4, "name": "Counterspell", "scryfall_id": "test"}
            ],
            "side": []
        }
        
        format_type = random.choice(["mtga", "moxfield", "archidekt", "tappedout"])
        with self.client.post(
            f"/api/export/{format_type}",
            json=deck_data,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")
    
    @task(2)
    def health_check(self):
        """Test health endpoint."""
        self.client.get("/health")
    
    @task(1)
    def get_metrics(self):
        """Test metrics endpoint."""
        self.client.get("/metrics")

class WebSocketUser(HttpUser):
    """WebSocket load test user."""
    
    wait_time = between(2, 5)
    
    def on_start(self):
        """Initialize WebSocket connection."""
        # Upload an image to get a job ID
        image = generate_test_image()
        response = self.client.post(
            "/api/ocr/upload",
            files={"file": ("test.png", image, "image/png")}
        )
        if response.status_code == 200:
            self.job_id = response.json().get("jobId")
        else:
            self.job_id = None
    
    @task
    def websocket_connection(self):
        """Test WebSocket connection."""
        if not self.job_id:
            return
        
        import websocket
        
        ws_url = f"ws://{self.host.replace('http://', '').replace('https://', '')}/ws/{self.job_id}"
        
        try:
            ws = websocket.create_connection(ws_url)
            
            # Send ping
            ws.send("ping")
            response = ws.recv()
            
            # Request status
            ws.send("status")
            status = ws.recv()
            
            # Wait for updates
            for _ in range(5):
                update = ws.recv()
                data = json.loads(update)
                if data.get("state") in ["completed", "failed"]:
                    break
                time.sleep(1)
            
            ws.close()
            
        except Exception as e:
            print(f"WebSocket error: {e}")

class StressTestUser(FastHttpUser):
    """Stress test user for finding breaking points."""
    
    wait_time = between(0.1, 0.5)  # Very aggressive
    
    @task
    def stress_upload(self):
        """Stress test with rapid uploads."""
        image = generate_test_image()
        self.client.post(
            "/api/ocr/upload",
            files={"file": ("stress.png", image, "image/png")}
        )

# Event handlers for statistics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log test start."""
    print("Load test starting...")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Log test statistics."""
    print("\nLoad test completed!")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failed requests: {environment.stats.total.num_failures}")
    print(f"Median response time: {environment.stats.total.median_response_time}ms")
    print(f"95% response time: {environment.stats.total.get_response_time_percentile(0.95)}ms")
    print(f"99% response time: {environment.stats.total.get_response_time_percentile(0.99)}ms")

# Custom test scenarios
class SpikeTestUser(FastHttpUser):
    """Spike test to simulate sudden traffic increase."""
    
    wait_time = between(0.5, 1)
    
    @task
    def spike_request(self):
        """Simulate spike traffic."""
        # Suddenly increase load
        for _ in range(10):
            image = generate_test_image()
            self.client.post(
                "/api/ocr/upload",
                files={"file": ("spike.png", image, "image/png")}
            )

class EnduranceTestUser(FastHttpUser):
    """Endurance test for long-running load."""
    
    wait_time = between(5, 10)  # Steady, sustainable load
    
    @task(50)
    def normal_workflow(self):
        """Simulate normal user workflow."""
        # Upload image
        image = generate_test_image()
        response = self.client.post(
            "/api/ocr/upload",
            files={"file": ("endurance.png", image, "image/png")}
        )
        
        if response.status_code == 200:
            job_id = response.json().get("jobId")
            
            # Poll for status
            for _ in range(10):
                status_response = self.client.get(f"/api/ocr/status/{job_id}")
                if status_response.status_code == 200:
                    data = status_response.json()
                    if data.get("state") in ["completed", "failed"]:
                        break
                time.sleep(2)
            
            # Export if completed
            if data.get("state") == "completed":
                self.client.post(
                    "/api/export/mtga",
                    json=data.get("result", {}).get("normalized", {})
                )
    
    @task(10)
    def background_health_checks(self):
        """Background health monitoring."""
        self.client.get("/health")
        self.client.get("/metrics")