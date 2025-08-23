#!/usr/bin/env python3
"""
Benchmark script for Screen2Deck OCR performance.
Tests accuracy, speed, and reliability across validation images.
"""

import os
import sys
import time
import json
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

@dataclass
class BenchmarkResult:
    """Single benchmark test result."""
    image: str
    format: str
    total_cards_expected: int
    total_cards_detected: int
    main_cards_detected: int
    side_cards_detected: int
    accuracy: float
    ocr_time_ms: float
    total_time_ms: float
    confidence: float
    vision_fallback_used: bool
    errors: List[str]

@dataclass
class BenchmarkSummary:
    """Overall benchmark summary."""
    total_tests: int
    passed_tests: int
    failed_tests: int
    avg_accuracy: float
    avg_ocr_time_ms: float
    avg_total_time_ms: float
    vision_fallback_rate: float
    error_rate: float
    results: List[BenchmarkResult]

# Expected results for validation images
EXPECTED_RESULTS = {
    "arena-standard.png": {
        "format": "MTGA",
        "main_cards": 60,
        "side_cards": 15,
        "sample_cards": ["Lightning Bolt", "Counterspell", "Island", "Mountain"]
    },
    "mtgo-modern.png": {
        "format": "MTGO",
        "main_cards": 60,
        "side_cards": 15,
        "sample_cards": ["Ragavan, Nimble Pilferer", "Murktide Regent", "Misty Rainforest"]
    },
    "partial-deck.png": {
        "format": "partial",
        "main_cards": 40,
        "side_cards": 0,
        "sample_cards": []
    },
    "oversized-deck.png": {
        "format": "commander",
        "main_cards": 100,
        "side_cards": 0,
        "sample_cards": []
    },
    "low-quality.jpg": {
        "format": "low-quality",
        "main_cards": 60,
        "side_cards": 15,
        "sample_cards": []
    },
    "empty-image.png": {
        "format": "empty",
        "main_cards": 0,
        "side_cards": 0,
        "sample_cards": []
    }
}

class Benchmark:
    """OCR benchmark runner."""
    
    def __init__(self, api_base: str = "http://localhost:8080"):
        self.api_base = api_base
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def health_check(self) -> bool:
        """Check if API is healthy."""
        try:
            async with self.session.get(f"{self.api_base}/health") as resp:
                return resp.status == 200
        except Exception as e:
            print(f"Health check failed: {e}")
            return False
    
    async def process_image(self, image_path: Path) -> Dict[str, Any]:
        """Process single image through OCR API."""
        start_time = time.time()
        
        # Upload image
        with open(image_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f, filename=image_path.name)
            
            async with self.session.post(
                f"{self.api_base}/api/ocr/upload",
                data=data
            ) as resp:
                if resp.status != 200:
                    return {"error": f"Upload failed: {resp.status}"}
                upload_result = await resp.json()
        
        job_id = upload_result.get("jobId")
        if not job_id:
            return {"error": "No job ID returned"}
        
        # Poll for results
        max_attempts = 30
        for attempt in range(max_attempts):
            await asyncio.sleep(1)
            
            async with self.session.get(
                f"{self.api_base}/api/ocr/status/{job_id}"
            ) as resp:
                if resp.status != 200:
                    continue
                    
                result = await resp.json()
                if result.get("status") == "completed":
                    result["total_time_ms"] = (time.time() - start_time) * 1000
                    return result
                elif result.get("status") == "failed":
                    return {"error": result.get("error", "Processing failed")}
        
        return {"error": "Timeout waiting for results"}
    
    def calculate_accuracy(self, detected: Dict, expected: Dict) -> float:
        """Calculate accuracy based on detected vs expected cards."""
        if expected["main_cards"] == 0:
            return 100.0 if detected.get("main_count", 0) == 0 else 0.0
        
        main_diff = abs(detected.get("main_count", 0) - expected["main_cards"])
        side_diff = abs(detected.get("side_count", 0) - expected["side_cards"])
        total_expected = expected["main_cards"] + expected["side_cards"]
        
        if total_expected == 0:
            return 100.0
        
        accuracy = max(0, 100 - ((main_diff + side_diff) / total_expected * 100))
        return accuracy
    
    async def run_benchmark(self, image_dir: Path) -> BenchmarkSummary:
        """Run benchmark on all images in directory."""
        results = []
        
        # Check health first
        if not await self.health_check():
            print("API health check failed!")
            return BenchmarkSummary(
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                avg_accuracy=0,
                avg_ocr_time_ms=0,
                avg_total_time_ms=0,
                vision_fallback_rate=0,
                error_rate=100,
                results=[]
            )
        
        # Process each image
        images = list(image_dir.glob("*.png")) + list(image_dir.glob("*.jpg"))
        for image_path in images:
            print(f"Processing {image_path.name}...")
            
            expected = EXPECTED_RESULTS.get(
                image_path.name,
                {"format": "unknown", "main_cards": 60, "side_cards": 15, "sample_cards": []}
            )
            
            result = await self.process_image(image_path)
            
            if "error" in result:
                benchmark_result = BenchmarkResult(
                    image=image_path.name,
                    format=expected["format"],
                    total_cards_expected=expected["main_cards"] + expected["side_cards"],
                    total_cards_detected=0,
                    main_cards_detected=0,
                    side_cards_detected=0,
                    accuracy=0,
                    ocr_time_ms=0,
                    total_time_ms=result.get("total_time_ms", 0),
                    confidence=0,
                    vision_fallback_used=False,
                    errors=[result["error"]]
                )
            else:
                # Parse result
                normalized = result.get("result", {}).get("normalized", {})
                main_count = sum(c.get("qty", 0) for c in normalized.get("main", []))
                side_count = sum(c.get("qty", 0) for c in normalized.get("side", []))
                
                # Check if Vision API was used
                raw_ocr = result.get("result", {}).get("raw", {})
                vision_used = raw_ocr.get("mean_conf", 0) >= 0.94  # Vision API returns 0.95
                
                accuracy = self.calculate_accuracy(
                    {"main_count": main_count, "side_count": side_count},
                    expected
                )
                
                benchmark_result = BenchmarkResult(
                    image=image_path.name,
                    format=expected["format"],
                    total_cards_expected=expected["main_cards"] + expected["side_cards"],
                    total_cards_detected=main_count + side_count,
                    main_cards_detected=main_count,
                    side_cards_detected=side_count,
                    accuracy=accuracy,
                    ocr_time_ms=result.get("result", {}).get("timings_ms", {}).get("ocr", 0),
                    total_time_ms=result.get("total_time_ms", 0),
                    confidence=raw_ocr.get("mean_conf", 0),
                    vision_fallback_used=vision_used,
                    errors=[]
                )
            
            results.append(benchmark_result)
            
            # Print result
            status = "✅" if benchmark_result.accuracy >= 85 else "❌"
            print(f"  {status} Accuracy: {benchmark_result.accuracy:.1f}%")
            print(f"     Cards: {benchmark_result.main_cards_detected}/{expected['main_cards']} main, "
                  f"{benchmark_result.side_cards_detected}/{expected['side_cards']} side")
            print(f"     Time: {benchmark_result.total_time_ms:.0f}ms (OCR: {benchmark_result.ocr_time_ms:.0f}ms)")
            print(f"     Vision: {'Yes' if benchmark_result.vision_fallback_used else 'No'}")
            print()
        
        # Calculate summary
        if results:
            passed = sum(1 for r in results if r.accuracy >= 85)
            failed = len(results) - passed
            avg_accuracy = sum(r.accuracy for r in results) / len(results)
            avg_ocr_time = sum(r.ocr_time_ms for r in results) / len(results)
            avg_total_time = sum(r.total_time_ms for r in results) / len(results)
            vision_rate = sum(1 for r in results if r.vision_fallback_used) / len(results) * 100
            error_rate = sum(1 for r in results if r.errors) / len(results) * 100
        else:
            passed = failed = 0
            avg_accuracy = avg_ocr_time = avg_total_time = vision_rate = error_rate = 0
        
        return BenchmarkSummary(
            total_tests=len(results),
            passed_tests=passed,
            failed_tests=failed,
            avg_accuracy=avg_accuracy,
            avg_ocr_time_ms=avg_ocr_time,
            avg_total_time_ms=avg_total_time,
            vision_fallback_rate=vision_rate,
            error_rate=error_rate,
            results=results
        )

async def main():
    """Run benchmark and print results."""
    image_dir = Path(__file__).parent.parent / "tests" / "validation-images"
    
    if not image_dir.exists():
        print(f"Error: Validation images not found at {image_dir}")
        return 1
    
    print("=" * 60)
    print("Screen2Deck OCR Benchmark")
    print("=" * 60)
    print()
    
    async with Benchmark() as benchmark:
        summary = await benchmark.run_benchmark(image_dir)
    
    # Print summary
    print("=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {summary.total_tests}")
    print(f"Passed: {summary.passed_tests} ({summary.passed_tests/max(1,summary.total_tests)*100:.1f}%)")
    print(f"Failed: {summary.failed_tests}")
    print()
    print(f"Average Accuracy: {summary.avg_accuracy:.1f}%")
    print(f"Average OCR Time: {summary.avg_ocr_time_ms:.0f}ms")
    print(f"Average Total Time: {summary.avg_total_time_ms:.0f}ms")
    print(f"Vision Fallback Rate: {summary.vision_fallback_rate:.1f}%")
    print(f"Error Rate: {summary.error_rate:.1f}%")
    print()
    
    # Save results to JSON
    output_file = Path(__file__).parent / "benchmark_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": asdict(summary)
        }, f, indent=2)
    print(f"Results saved to {output_file}")
    
    return 0 if summary.passed_tests > summary.failed_tests else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)