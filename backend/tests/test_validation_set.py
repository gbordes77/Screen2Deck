import os, time, requests
from pathlib import Path
BASE = os.getenv("API_BASE", "http://localhost:8080")
IMG_DIR = Path("validation_set")
def test_all():
    imgs = list(IMG_DIR.glob("*")); assert imgs, "Placez vos images dans validation_set/"
    for p in imgs:
        with open(p, "rb") as f:
            r = requests.post(f"{BASE}/api/ocr/upload", files={"file": f}); r.raise_for_status()
            jobId = r.json()["jobId"]
        for _ in range(50):
            s = requests.get(f"{BASE}/api/ocr/status/{jobId}").json()
            if s["state"] == "completed": break
            time.sleep(0.1)
        else: raise AssertionError("Timeout " + p.name)