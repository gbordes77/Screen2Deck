#!/usr/bin/env python3
"""Benchmark runner for Screen2Deck OCR performance."""
import argparse
import json
import time
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

from benchlib import evaluate_dir

def main():
    ap = argparse.ArgumentParser(description="Run OCR benchmarks and generate metrics")
    ap.add_argument("--images", required=True, help="Directory containing test images")
    ap.add_argument("--truth", required=True, help="Directory containing ground truth files")
    ap.add_argument("--out", required=True, help="Output directory for reports")
    ap.add_argument("--vision", action="store_true", help="Enable Vision API fallback")
    args = ap.parse_args()
    
    # Create output directory
    outdir = pathlib.Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Run evaluation
    print(f"Running benchmark on {args.images}...")
    metrics = evaluate_dir(
        pathlib.Path(args.images),
        pathlib.Path(args.truth),
        outdir,
        use_vision_fallback=args.vision
    )
    
    # Save metrics
    metrics_file = outdir / "metrics.json"
    metrics_file.write_text(json.dumps(metrics, indent=2), encoding="utf8")
    
    # Print summary
    print("\n=== Benchmark Results ===")
    print(json.dumps(metrics, indent=2))
    
    # Check against SLOs
    slo_passed = True
    if metrics.get("card_ident_acc", 0) < 0.93:
        print(f"⚠️  Accuracy {metrics['card_ident_acc']:.1%} below SLO (93%)")
        slo_passed = False
    else:
        print(f"✅ Accuracy {metrics['card_ident_acc']:.1%} meets SLO")
    
    if metrics.get("p95_latency_sec", 999) > 5.0:
        print(f"⚠️  P95 latency {metrics['p95_latency_sec']:.1f}s above SLO (5s)")
        slo_passed = False
    else:
        print(f"✅ P95 latency {metrics['p95_latency_sec']:.1f}s meets SLO")
    
    # Generate HTML report
    html_report = outdir / "report.html"
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Screen2Deck Benchmark Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; }}
        .metric {{ background: #f0f0f0; padding: 20px; margin: 10px 0; border-radius: 8px; }}
        .pass {{ color: green; }}
        .fail {{ color: red; }}
        h1 {{ color: #333; }}
        pre {{ background: #282c34; color: #abb2bf; padding: 15px; border-radius: 5px; overflow-x: auto; }}
    </style>
</head>
<body>
    <h1>🎴 Screen2Deck OCR Benchmark Report</h1>
    
    <div class="metric">
        <h2>📊 Summary</h2>
        <ul>
            <li>Images processed: {metrics.get('images', 0)}</li>
            <li>Vision fallback: {'Enabled' if args.vision else 'Disabled'}</li>
            <li>Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}</li>
        </ul>
    </div>
    
    <div class="metric">
        <h2>🎯 Accuracy</h2>
        <p class="{'pass' if metrics.get('card_ident_acc', 0) >= 0.93 else 'fail'}">
            Card Identification: {metrics.get('card_ident_acc', 0):.1%}
            (SLO: ≥93%)
        </p>
    </div>
    
    <div class="metric">
        <h2>⚡ Performance</h2>
        <ul>
            <li>P50 Latency: {metrics.get('p50_latency_sec', 0):.2f}s</li>
            <li class="{'pass' if metrics.get('p95_latency_sec', 999) <= 5.0 else 'fail'}">
                P95 Latency: {metrics.get('p95_latency_sec', 0):.2f}s (SLO: ≤5s)
            </li>
        </ul>
    </div>
    
    <div class="metric">
        <h2>📝 Raw Metrics</h2>
        <pre>{json.dumps(metrics, indent=2)}</pre>
    </div>
</body>
</html>"""
    
    html_report.write_text(html_content, encoding="utf8")
    print(f"\n📄 HTML report: {html_report}")
    
    return 0 if slo_passed else 1

if __name__ == "__main__":
    sys.exit(main())