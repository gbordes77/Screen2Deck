#!/usr/bin/env python3
"""
E2E Benchmark Runner for Screen2Deck
Validates OCR accuracy and performance against golden test set
"""

import json
import time
import hashlib
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
import asyncio
import aiohttp
from tabulate import tabulate
from datetime import datetime

@dataclass
class BenchmarkResult:
    """Single image benchmark result"""
    image_name: str
    image_hash: str
    total_time_ms: float
    ocr_time_ms: float
    match_time_ms: float
    
    # Accuracy metrics
    main_expected: int
    main_found: int
    main_correct: int
    side_expected: int
    side_found: int
    side_correct: int
    
    # Quality metrics
    exact_accuracy: float  # Exact name match
    lenient_accuracy: float  # Fuzzy match > 90%
    confidence_mean: float
    confidence_min: float
    
    # Operational
    fallback_used: bool
    cache_hits: int
    errors: List[str]
    
    @property
    def passed(self) -> bool:
        """Check if test passed acceptance criteria"""
        return (
            self.exact_accuracy >= 0.95 and
            self.total_time_ms < 5000 and
            len(self.errors) == 0
        )

class E2EBenchRunner:
    """End-to-end benchmark runner"""
    
    def __init__(self, api_url: str = "http://localhost:8080"):
        self.api_url = api_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    def calculate_hash(self, image_path: Path) -> str:
        """Calculate SHA-256 hash of image"""
        sha256 = hashlib.sha256()
        with open(image_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    async def upload_image(self, image_path: Path) -> Tuple[str, float]:
        """Upload image and return job_id with timing"""
        start = time.perf_counter()
        
        with open(image_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f, filename=image_path.name,
                          content_type='image/jpeg')
            
            async with self.session.post(
                f"{self.api_url}/api/ocr/upload",
                data=data
            ) as resp:
                result = await resp.json()
                elapsed = (time.perf_counter() - start) * 1000
                return result['jobId'], elapsed
    
    async def poll_status(self, job_id: str, timeout: int = 30) -> Dict:
        """Poll job status until complete"""
        start = time.perf_counter()
        
        while (time.perf_counter() - start) < timeout:
            async with self.session.get(
                f"{self.api_url}/api/ocr/status/{job_id}"
            ) as resp:
                result = await resp.json()
                
                if result['state'] in ['completed', 'failed']:
                    return result
                    
            await asyncio.sleep(0.5)
        
        raise TimeoutError(f"Job {job_id} timed out after {timeout}s")
    
    def load_golden(self, golden_path: Path) -> Dict:
        """Load golden deck list"""
        with open(golden_path, 'r') as f:
            return json.load(f)
    
    def calculate_accuracy(self, found: Dict, expected: Dict) -> Tuple[float, float]:
        """Calculate exact and lenient accuracy"""
        from rapidfuzz import fuzz
        
        # Build card lists
        found_cards = []
        for card in found.get('main', []) + found.get('side', []):
            for _ in range(card.get('qty', 1)):
                found_cards.append(card['name'].lower())
        
        expected_cards = []
        for card in expected.get('main', []) + expected.get('side', []):
            for _ in range(card.get('qty', 1)):
                expected_cards.append(card['name'].lower())
        
        if not expected_cards:
            return 0.0, 0.0
        
        # Exact matching
        exact_matches = 0
        lenient_matches = 0
        
        for expected in expected_cards:
            if expected in found_cards:
                exact_matches += 1
                lenient_matches += 1
                found_cards.remove(expected)
            else:
                # Try fuzzy match for lenient
                best_match = None
                best_score = 0
                for found in found_cards:
                    score = fuzz.ratio(expected, found)
                    if score > best_score:
                        best_score = score
                        best_match = found
                
                if best_score >= 90:
                    lenient_matches += 1
                    if best_match:
                        found_cards.remove(best_match)
        
        exact_accuracy = exact_matches / len(expected_cards)
        lenient_accuracy = lenient_matches / len(expected_cards)
        
        return exact_accuracy, lenient_accuracy
    
    async def benchmark_image(self, image_path: Path, golden: Dict) -> BenchmarkResult:
        """Benchmark single image"""
        image_hash = self.calculate_hash(image_path)
        errors = []
        
        try:
            # Upload and process
            job_id, upload_time = await self.upload_image(image_path)
            result = await self.poll_status(job_id)
            
            if result['state'] == 'failed':
                errors.append(f"OCR failed: {result.get('error', 'Unknown')}")
                return BenchmarkResult(
                    image_name=image_path.name,
                    image_hash=image_hash,
                    total_time_ms=upload_time,
                    ocr_time_ms=0,
                    match_time_ms=0,
                    main_expected=len(golden.get('main', [])),
                    main_found=0,
                    main_correct=0,
                    side_expected=len(golden.get('side', [])),
                    side_found=0,
                    side_correct=0,
                    exact_accuracy=0,
                    lenient_accuracy=0,
                    confidence_mean=0,
                    confidence_min=0,
                    fallback_used=False,
                    cache_hits=0,
                    errors=errors
                )
            
            # Extract metrics
            ocr_result = result.get('result', {})
            normalized = ocr_result.get('normalized', {})
            metrics = result.get('metrics', {})
            
            # Calculate timing
            total_time = metrics.get('total_time_ms', upload_time)
            ocr_time = metrics.get('ocr_time_ms', 0)
            match_time = metrics.get('match_time_ms', 0)
            
            # Calculate accuracy
            exact_acc, lenient_acc = self.calculate_accuracy(normalized, golden)
            
            # Count cards
            main_found = normalized.get('main', [])
            side_found = normalized.get('side', [])
            
            # Calculate correct counts (simplified)
            main_correct = int(exact_acc * len(golden.get('main', [])))
            side_correct = int(exact_acc * len(golden.get('side', [])))
            
            # Get confidence metrics
            confidence_mean = metrics.get('confidence_mean', 0)
            confidence_min = metrics.get('confidence_min', 0)
            
            return BenchmarkResult(
                image_name=image_path.name,
                image_hash=image_hash,
                total_time_ms=total_time,
                ocr_time_ms=ocr_time,
                match_time_ms=match_time,
                main_expected=sum(c['qty'] for c in golden.get('main', [])),
                main_found=sum(c['qty'] for c in main_found),
                main_correct=main_correct,
                side_expected=sum(c['qty'] for c in golden.get('side', [])),
                side_found=sum(c['qty'] for c in side_found),
                side_correct=side_correct,
                exact_accuracy=exact_acc,
                lenient_accuracy=lenient_acc,
                confidence_mean=confidence_mean,
                confidence_min=confidence_min,
                fallback_used=metrics.get('fallback_used', False),
                cache_hits=metrics.get('cache_hits', 0),
                errors=errors
            )
            
        except Exception as e:
            errors.append(str(e))
            return BenchmarkResult(
                image_name=image_path.name,
                image_hash=image_hash,
                total_time_ms=0,
                ocr_time_ms=0,
                match_time_ms=0,
                main_expected=len(golden.get('main', [])),
                main_found=0,
                main_correct=0,
                side_expected=len(golden.get('side', [])),
                side_found=0,
                side_correct=0,
                exact_accuracy=0,
                lenient_accuracy=0,
                confidence_mean=0,
                confidence_min=0,
                fallback_used=False,
                cache_hits=0,
                errors=errors
            )
    
    async def run_benchmark(self, images_dir: Path, golden_dir: Path) -> List[BenchmarkResult]:
        """Run benchmark on all images"""
        results = []
        
        # Find all images
        image_files = sorted(images_dir.glob("*.jpg")) + \
                     sorted(images_dir.glob("*.jpeg")) + \
                     sorted(images_dir.glob("*.png")) + \
                     sorted(images_dir.glob("*.webp"))
        
        print(f"Found {len(image_files)} images to benchmark")
        
        for image_path in image_files:
            # Find corresponding golden file
            golden_path = golden_dir / f"{image_path.stem}.json"
            if not golden_path.exists():
                print(f"⚠️  No golden file for {image_path.name}, skipping")
                continue
            
            print(f"📸 Benchmarking {image_path.name}...")
            golden = self.load_golden(golden_path)
            result = await self.benchmark_image(image_path, golden)
            results.append(result)
            
            # Print quick status
            status = "✅" if result.passed else "❌"
            print(f"  {status} Accuracy: {result.exact_accuracy:.1%} | Time: {result.total_time_ms:.0f}ms")
        
        return results
    
    def generate_report(self, results: List[BenchmarkResult]) -> Dict:
        """Generate benchmark report"""
        # Calculate aggregates
        total_images = len(results)
        passed_images = sum(1 for r in results if r.passed)
        
        avg_accuracy = sum(r.exact_accuracy for r in results) / total_images if total_images > 0 else 0
        avg_lenient = sum(r.lenient_accuracy for r in results) / total_images if total_images > 0 else 0
        avg_time = sum(r.total_time_ms for r in results) / total_images if total_images > 0 else 0
        p95_time = sorted([r.total_time_ms for r in results])[int(total_images * 0.95)] if total_images > 0 else 0
        
        fallback_count = sum(1 for r in results if r.fallback_used)
        total_errors = sum(len(r.errors) for r in results)
        
        return {
            "summary": {
                "total_images": total_images,
                "passed": passed_images,
                "failed": total_images - passed_images,
                "pass_rate": passed_images / total_images if total_images > 0 else 0,
                "avg_exact_accuracy": avg_accuracy,
                "avg_lenient_accuracy": avg_lenient,
                "avg_time_ms": avg_time,
                "p95_time_ms": p95_time,
                "fallback_usage": fallback_count,
                "total_errors": total_errors
            },
            "acceptance": {
                "target_accuracy": 0.95,
                "target_p95_ms": 5000,
                "target_pass_rate": 0.8,
                "passed": (
                    avg_accuracy >= 0.95 and
                    p95_time <= 5000 and
                    passed_images / total_images >= 0.8
                ) if total_images > 0 else False
            },
            "details": [asdict(r) for r in results]
        }
    
    def print_report(self, report: Dict):
        """Print human-readable report"""
        summary = report['summary']
        acceptance = report['acceptance']
        
        print("\n" + "="*80)
        print("📊 BENCHMARK REPORT - Screen2Deck E2E Validation")
        print("="*80)
        
        # Summary table
        summary_data = [
            ["Total Images", summary['total_images']],
            ["Passed", f"{summary['passed']} ({summary['pass_rate']:.1%})"],
            ["Failed", summary['failed']],
            ["Avg Exact Accuracy", f"{summary['avg_exact_accuracy']:.1%}"],
            ["Avg Lenient Accuracy", f"{summary['avg_lenient_accuracy']:.1%}"],
            ["Avg Time", f"{summary['avg_time_ms']:.0f}ms"],
            ["P95 Time", f"{summary['p95_time_ms']:.0f}ms"],
            ["Fallback Used", summary['fallback_usage']],
            ["Total Errors", summary['total_errors']]
        ]
        print("\n📈 Summary:")
        print(tabulate(summary_data, headers=["Metric", "Value"], tablefmt="grid"))
        
        # Acceptance criteria
        print(f"\n✅ Acceptance Criteria: {'PASSED' if acceptance['passed'] else 'FAILED'}")
        print(f"  - Target Accuracy: ≥{acceptance['target_accuracy']:.0%} (got {summary['avg_exact_accuracy']:.1%})")
        print(f"  - Target P95 Time: ≤{acceptance['target_p95_ms']}ms (got {summary['p95_time_ms']:.0f}ms)")
        print(f"  - Target Pass Rate: ≥{acceptance['target_pass_rate']:.0%} (got {summary['pass_rate']:.1%})")
        
        # Details table
        details_data = []
        for r in report['details']:
            details_data.append([
                r['image_name'][:30],
                f"{r['exact_accuracy']:.1%}",
                f"{r['total_time_ms']:.0f}ms",
                f"{r['main_found']}/{r['main_expected']}",
                "✅" if r['exact_accuracy'] >= 0.95 and r['total_time_ms'] < 5000 else "❌"
            ])
        
        print("\n📋 Details by Image:")
        print(tabulate(details_data, 
                      headers=["Image", "Accuracy", "Time", "Cards", "Pass"],
                      tablefmt="grid"))

async def main():
    parser = argparse.ArgumentParser(description="Screen2Deck E2E Benchmark Runner")
    parser.add_argument("--images", type=Path, default="./decklist-validation-set",
                       help="Directory containing test images")
    parser.add_argument("--golden", type=Path, default="./validation_set/golden",
                       help="Directory containing golden JSON files")
    parser.add_argument("--out", type=Path, default="./reports",
                       help="Output directory for reports")
    parser.add_argument("--api-url", default="http://localhost:8080",
                       help="API base URL")
    
    args = parser.parse_args()
    
    # Ensure directories exist
    args.out.mkdir(parents=True, exist_ok=True)
    
    # Run benchmark
    async with E2EBenchRunner(args.api_url) as runner:
        results = await runner.run_benchmark(args.images, args.golden)
        report = runner.generate_report(results)
        
        # Save JSON report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = args.out / f"benchmark_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Save Markdown report
        md_path = args.out / f"benchmark_{timestamp}.md"
        with open(md_path, 'w') as f:
            f.write(f"# Screen2Deck Benchmark Report\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write(f"## Summary\n")
            f.write(f"- **Pass Rate**: {report['summary']['pass_rate']:.1%}\n")
            f.write(f"- **Avg Accuracy**: {report['summary']['avg_exact_accuracy']:.1%}\n")
            f.write(f"- **P95 Time**: {report['summary']['p95_time_ms']:.0f}ms\n")
            f.write(f"- **Acceptance**: {'✅ PASSED' if report['acceptance']['passed'] else '❌ FAILED'}\n")
        
        # Print report
        runner.print_report(report)
        
        print(f"\n📁 Reports saved to:")
        print(f"  - JSON: {json_path}")
        print(f"  - Markdown: {md_path}")
        
        # Exit with appropriate code
        exit(0 if report['acceptance']['passed'] else 1)

if __name__ == "__main__":
    asyncio.run(main())