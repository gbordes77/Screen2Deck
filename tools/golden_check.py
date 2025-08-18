#!/usr/bin/env python3
"""Golden exports checker - compare current exports against references."""
import argparse
import json
import pathlib
import sys
from goldenlib import compare_all_targets

def main():
    ap = argparse.ArgumentParser(description="Check export formats against golden references")
    ap.add_argument("--out", required=True, help="Output directory for results")
    ap.add_argument("--reference", default="golden_exports/reference", help="Reference exports directory")
    ap.add_argument("--current", default="golden_exports/current", help="Current exports directory")
    args = ap.parse_args()
    
    outdir = pathlib.Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    
    print("🔍 Checking export formats against golden references...")
    
    results = compare_all_targets(args.reference, args.current)
    
    # Save results
    results_file = outdir / "golden_results.json"
    results_file.write_text(json.dumps(results, indent=2), encoding="utf8")
    
    # Print summary
    all_pass = True
    for fmt, result in results.items():
        if result["equal"]:
            print(f"✅ {fmt.upper()}: PASS")
        else:
            print(f"❌ {fmt.upper()}: FAIL")
            if result.get("diff"):
                print(f"   Diff: {result['diff'][:200]}...")
            all_pass = False
    
    # Generate HTML report
    html_report = outdir / "golden_report.html"
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Golden Export Tests</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 40px; }}
        .pass {{ background: #d4edda; padding: 10px; margin: 5px 0; }}
        .fail {{ background: #f8d7da; padding: 10px; margin: 5px 0; }}
        pre {{ background: #f4f4f4; padding: 10px; overflow-x: auto; }}
    </style>
</head>
<body>
    <h1>🏆 Golden Export Test Results</h1>
    <p>Timestamp: {pathlib.Path(__file__).stat().st_mtime}</p>
    
    {"".join([
        f'<div class="{"pass" if r["equal"] else "fail"}">'
        f'<h3>{fmt.upper()}: {"✅ PASS" if r["equal"] else "❌ FAIL"}</h3>'
        f'{"<pre>" + str(r.get("diff", ""))[:500] + "</pre>" if not r["equal"] else ""}'
        f'</div>'
        for fmt, r in results.items()
    ])}
    
    <h2>Raw Results</h2>
    <pre>{json.dumps(results, indent=2)}</pre>
</body>
</html>"""
    
    html_report.write_text(html_content, encoding="utf8")
    print(f"\n📄 Report saved to {html_report}")
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())