#!/usr/bin/env python3
"""
Independent benchmark script for Screen2Deck
Calculates real metrics without relying on backend self-reported values
"""

import json
import time
import hashlib
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import argparse
from datetime import datetime
import difflib

class IndependentBenchmark:
    """Benchmark tool that measures from client perspective"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip('/')
        self.results = []
        self.cache_hits = 0
        self.cache_misses = 0
        
    def upload_image(self, image_path: Path) -> Tuple[str, float]:
        """Upload image and return job_id with timing"""
        start = time.time()
        
        with open(image_path, 'rb') as f:
            files = {'file': (image_path.name, f, 'image/png')}
            response = requests.post(f"{self.base_url}/api/ocr/upload", files=files)
            
        elapsed = time.time() - start
        response.raise_for_status()
        data = response.json()
        
        # Check if this was cached
        if data.get('cached', False):
            self.cache_hits += 1
        else:
            self.cache_misses += 1
            
        return data['jobId'], elapsed
    
    def wait_for_result(self, job_id: str, timeout: int = 30) -> Tuple[Optional[Dict], float]:
        """Poll for result and return with total processing time"""
        start = time.time()
        poll_count = 0
        
        while time.time() - start < timeout:
            poll_count += 1
            # Progressive polling like the frontend
            interval = min(0.5 + (poll_count * 0.25), 2.0)
            
            response = requests.get(f"{self.base_url}/api/ocr/status/{job_id}")
            if response.status_code == 200:
                data = response.json()
                if data.get('state') == 'completed':
                    elapsed = time.time() - start
                    return data.get('result'), elapsed
                elif data.get('state') == 'failed':
                    return None, time.time() - start
            
            time.sleep(interval)
        
        return None, timeout
    
    def calculate_accuracy(self, detected: List[Dict], expected: List[Dict]) -> float:
        """Calculate card detection accuracy"""
        if not expected:
            return 0.0
        
        # Normalize card names for comparison
        detected_cards = set()
        for card in detected:
            name = card.get('name', '').lower().strip()
            qty = card.get('qty', 1)
            detected_cards.add(f"{qty}x {name}")
        
        expected_cards = set()
        for card in expected:
            name = card.get('name', '').lower().strip()
            qty = card.get('qty', 1)
            expected_cards.add(f"{qty}x {name}")
        
        # Calculate exact matches
        matches = detected_cards & expected_cards
        accuracy = len(matches) / len(expected_cards) if expected_cards else 0
        
        return accuracy * 100
    
    def calculate_fuzzy_accuracy(self, detected: List[Dict], expected: List[Dict]) -> float:
        """Calculate accuracy with fuzzy matching for partial matches"""
        if not expected:
            return 0.0
        
        matched = 0
        for exp_card in expected:
            exp_name = exp_card.get('name', '').lower().strip()
            exp_qty = exp_card.get('qty', 1)
            
            # Find best match in detected
            best_ratio = 0
            for det_card in detected:
                det_name = det_card.get('name', '').lower().strip()
                det_qty = det_card.get('qty', 1)
                
                # Check quantity match
                if det_qty == exp_qty:
                    # Calculate name similarity
                    ratio = difflib.SequenceMatcher(None, exp_name, det_name).ratio()
                    best_ratio = max(best_ratio, ratio)
            
            # Consider matched if >85% similar
            if best_ratio > 0.85:
                matched += 1
        
        return (matched / len(expected)) * 100
    
    def load_golden_data(self, image_path: Path) -> Optional[List[Dict]]:
        """Load expected golden data for an image"""
        golden_path = image_path.parent / 'golden' / f"{image_path.stem}.json"
        if golden_path.exists():
            with open(golden_path) as f:
                data = json.load(f)
                # Extract cards from the golden format
                if 'normalized' in data:
                    main = data['normalized'].get('main', [])
                    side = data['normalized'].get('side', [])
                    return main + side
                return data.get('cards', [])
        return None
    
    def benchmark_image(self, image_path: Path) -> Dict:
        """Run benchmark for a single image"""
        print(f"Testing: {image_path.name}")
        
        # Get expected results
        expected = self.load_golden_data(image_path)
        
        # Upload and measure
        job_id, upload_time = self.upload_image(image_path)
        result, processing_time = self.wait_for_result(job_id)
        
        total_time = upload_time + processing_time
        
        # Calculate accuracy if we have golden data
        accuracy = 0
        fuzzy_accuracy = 0
        if result and expected:
            detected = result.get('normalized', {}).get('main', [])
            detected.extend(result.get('normalized', {}).get('side', []))
            
            accuracy = self.calculate_accuracy(detected, expected)
            fuzzy_accuracy = self.calculate_fuzzy_accuracy(detected, expected)
        
        # Store result
        test_result = {
            'image': image_path.name,
            'job_id': job_id,
            'upload_time': upload_time,
            'processing_time': processing_time,
            'total_time': total_time,
            'accuracy': accuracy,
            'fuzzy_accuracy': fuzzy_accuracy,
            'success': result is not None,
            'card_count': len(result.get('normalized', {}).get('main', [])) if result else 0,
            'has_golden': expected is not None
        }
        
        self.results.append(test_result)
        return test_result
    
    def run_benchmark(self, image_dir: Path, pattern: str = "*.png") -> Dict:
        """Run benchmark on all images in directory"""
        self.image_dir = image_dir  # Store for SHA256 calculation
        images = list(image_dir.glob(pattern))
        print(f"Found {len(images)} images to test")
        
        for image_path in images:
            try:
                self.benchmark_image(image_path)
            except Exception as e:
                print(f"Error testing {image_path}: {e}")
                self.results.append({
                    'image': image_path.name,
                    'error': str(e),
                    'success': False
                })
        
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        """Generate benchmark report with real metrics"""
        successful = [r for r in self.results if r.get('success')]
        
        if not successful:
            return {'error': 'No successful tests'}
        
        # Calculate metrics
        total_times = [r['total_time'] for r in successful]
        accuracies = [r['accuracy'] for r in successful if r.get('has_golden')]
        fuzzy_accuracies = [r['fuzzy_accuracy'] for r in successful if r.get('has_golden')]
        
        # Calculate percentiles
        total_times_sorted = sorted(total_times)
        p50_idx = int(len(total_times_sorted) * 0.5)
        p95_idx = int(len(total_times_sorted) * 0.95)
        p99_idx = int(len(total_times_sorted) * 0.99)
        
        # Get provenance information
        import subprocess
        import platform
        import sys
        import glob
        
        try:
            git_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()[:8]
        except:
            git_sha = 'unknown'
        
        try:
            docker_image = subprocess.check_output(['docker', 'images', '-q', 'screen2deck-backend:latest'], text=True).strip()[:12]
        except:
            docker_image = 'unknown'
        
        # Calculate dataset SHA256
        def calculate_dataset_sha256(path):
            """Calculate SHA256 of all images in dataset"""
            h = hashlib.sha256()
            image_files = sorted(glob.glob(os.path.join(path, '*')))
            for img_path in image_files:
                if os.path.isfile(img_path):
                    with open(img_path, 'rb') as f:
                        # Hash the hash of each file (for efficiency)
                        file_hash = hashlib.sha256(f.read()).digest()
                        h.update(file_hash)
            return h.hexdigest()
        
        dataset_sha = 'unknown'
        if hasattr(self, 'image_dir') and self.image_dir:
            dataset_sha = calculate_dataset_sha256(self.image_dir)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'provenance': {
                'git_sha': git_sha,
                'docker_image': docker_image,
                's2d_ver': os.getenv('S2D_VERSION', git_sha),
                'api_url': self.base_url,
                'dataset_sha256': dataset_sha,
                'env': {
                    'python': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                    'easyocr': '1.7.1',
                    'platform': platform.platform(),
                    'threads': os.getenv('S2D_THREADS', '1'),
                    'deterministic': os.getenv('DETERMINISTIC_MODE', 'off'),
                    'seed': os.getenv('S2D_SEED', '42'),
                },
                'feature_flags': {
                    'ocr_engine': os.getenv('OCR_ENGINE', 'easyocr'),
                    'vision_fallback': os.getenv('VISION_OCR_FALLBACK', 'off'),
                    'fuzzy_strict': os.getenv('FUZZY_STRICT_MODE', 'on'),
                    'scryfall_online': os.getenv('SCRYFALL_ONLINE', 'off'),
                }
            },
            'summary': {
                'total_tests': len(self.results),
                'successful': len(successful),
                'failed': len(self.results) - len(successful),
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'cache_hit_rate': self.cache_hits / len(self.results) if self.results else 0
            },
            'latency': {
                'mean': statistics.mean(total_times),
                'median': statistics.median(total_times),
                'p50': total_times_sorted[p50_idx] if p50_idx < len(total_times_sorted) else 0,
                'p95': total_times_sorted[p95_idx] if p95_idx < len(total_times_sorted) else 0,
                'p99': total_times_sorted[p99_idx] if p99_idx < len(total_times_sorted) else 0,
                'min': min(total_times),
                'max': max(total_times)
            },
            'accuracy': {
                'exact_match': {
                    'mean': statistics.mean(accuracies) if accuracies else 0,
                    'median': statistics.median(accuracies) if accuracies else 0,
                    'min': min(accuracies) if accuracies else 0,
                    'max': max(accuracies) if accuracies else 0
                },
                'fuzzy_match': {
                    'mean': statistics.mean(fuzzy_accuracies) if fuzzy_accuracies else 0,
                    'median': statistics.median(fuzzy_accuracies) if fuzzy_accuracies else 0,
                    'min': min(fuzzy_accuracies) if fuzzy_accuracies else 0,
                    'max': max(fuzzy_accuracies) if fuzzy_accuracies else 0
                }
            },
            'details': self.results
        }
        
        return report
    
    def check_prometheus_metrics(self) -> Optional[Dict]:
        """Fetch and parse Prometheus metrics if available"""
        try:
            response = requests.get(f"{self.base_url}/metrics", timeout=2)
            if response.status_code == 200:
                metrics = {}
                for line in response.text.split('\n'):
                    if 'screen2deck_' in line and not line.startswith('#'):
                        parts = line.split(' ')
                        if len(parts) == 2:
                            metrics[parts[0]] = float(parts[1])
                return metrics
        except:
            pass
        return None

def main():
    parser = argparse.ArgumentParser(description='Independent Screen2Deck benchmark')
    parser.add_argument('--images', type=Path, default=Path('./validation_set'),
                       help='Directory containing test images')
    parser.add_argument('--output', type=Path, default=Path('./reports/independent_bench.json'),
                       help='Output file for results')
    parser.add_argument('--url', default='http://localhost:8080',
                       help='Backend URL')
    parser.add_argument('--pattern', default='*.png',
                       help='Image file pattern')
    
    args = parser.parse_args()
    
    # Create output directory if needed
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    # Run benchmark
    bench = IndependentBenchmark(args.url)
    
    print(f"Starting independent benchmark...")
    print(f"Backend: {args.url}")
    print(f"Images: {args.images}")
    print("-" * 60)
    
    # Check if backend is running
    try:
        health = requests.get(f"{args.url}/health", timeout=2)
        if health.status_code != 200:
            print("ERROR: Backend not healthy!")
            return 1
    except Exception as e:
        print(f"ERROR: Cannot connect to backend: {e}")
        return 1
    
    # Run tests
    report = bench.run_benchmark(args.images, args.pattern)
    
    # Check Prometheus metrics
    prometheus = bench.check_prometheus_metrics()
    if prometheus:
        report['prometheus_metrics'] = prometheus
        print(f"\nPrometheus metrics found:")
        for key, value in prometheus.items():
            if 'cache' in key or 'accuracy' in key:
                print(f"  {key}: {value}")
    
    # Save report
    with open(args.output, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 60)
    print("INDEPENDENT BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Tests run: {report['summary']['total_tests']}")
    print(f"Successful: {report['summary']['successful']}")
    print(f"Failed: {report['summary']['failed']}")
    print(f"\nCache Performance:")
    print(f"  Hit rate: {report['summary']['cache_hit_rate']:.1%}")
    print(f"  Hits: {report['summary']['cache_hits']}")
    print(f"  Misses: {report['summary']['cache_misses']}")
    print(f"\nLatency (seconds):")
    print(f"  Mean: {report['latency']['mean']:.2f}s")
    print(f"  P50: {report['latency']['p50']:.2f}s")
    print(f"  P95: {report['latency']['p95']:.2f}s")
    print(f"  P99: {report['latency']['p99']:.2f}s")
    print(f"\nAccuracy (exact match):")
    print(f"  Mean: {report['accuracy']['exact_match']['mean']:.1f}%")
    print(f"  Median: {report['accuracy']['exact_match']['median']:.1f}%")
    print(f"\nAccuracy (fuzzy match >85%):")
    print(f"  Mean: {report['accuracy']['fuzzy_match']['mean']:.1f}%")
    print(f"  Median: {report['accuracy']['fuzzy_match']['median']:.1f}%")
    print("=" * 60)
    print(f"Report saved to: {args.output}")
    
    # Return non-zero if accuracy is suspiciously high or low
    exact_accuracy = report['accuracy']['exact_match']['mean']
    if exact_accuracy > 95:
        print("\n⚠️  WARNING: Accuracy suspiciously high - verify golden data!")
        return 2
    elif exact_accuracy < 40:
        print("\n⚠️  WARNING: Accuracy below 40% - system may have issues!")
        return 3
    
    return 0

if __name__ == '__main__':
    exit(main())