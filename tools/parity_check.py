#!/usr/bin/env python3
"""Parity checker - ensure web and Discord produce identical exports."""
import argparse
import json
import pathlib
import sys
from paritylib import check_parity

def main():
    ap = argparse.ArgumentParser(description="Check web/Discord export parity")
    ap.add_argument("--out", required=True, help="Output directory for results")
    ap.add_argument("--fixture", default="fixtures/normalized_deck.json", help="Normalized deck fixture")
    args = ap.parse_args()
    
    outdir = pathlib.Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    
    print("🔄 Checking Web/Discord parity...")
    
    ok, results = check_parity(args.fixture)
    
    # Save results
    results_file = outdir / "parity_results.json"
    results_file.write_text(json.dumps(results, indent=2), encoding="utf8")
    
    # Print summary
    if ok:
        print("✅ Web and Discord produce identical exports!")
    else:
        print("❌ Web and Discord exports differ!")
        for fmt, diff in results.get("differences", {}).items():
            print(f"  - {fmt}: {diff}")
    
    # Generate HTML report
    html_report = outdir / "parity_report.html"
    status_color = "green" if ok else "red"
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Web/Discord Parity Test</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 40px; }}
        .status {{ color: {status_color}; font-size: 24px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f4f4f4; }}
        .pass {{ background: #d4edda; }}
        .fail {{ background: #f8d7da; }}
    </style>
</head>
<body>
    <h1>🔄 Web/Discord Export Parity Test</h1>
    <p class="status">{"✅ PASS" if ok else "❌ FAIL"}</p>
    
    <table>
        <tr>
            <th>Format</th>
            <th>Web Hash</th>
            <th>Discord Hash</th>
            <th>Match</th>
        </tr>
        {"".join([
            f'<tr class="{"pass" if r.get("match") else "fail"}">'
            f'<td>{fmt.upper()}</td>'
            f'<td><code>{r.get("web_hash", "N/A")[:8]}...</code></td>'
            f'<td><code>{r.get("discord_hash", "N/A")[:8]}...</code></td>'
            f'<td>{"✅" if r.get("match") else "❌"}</td>'
            f'</tr>'
            for fmt, r in results.get("formats", {}).items()
        ])}
    </table>
    
    <h2>Test Details</h2>
    <pre>{json.dumps(results, indent=2)}</pre>
</body>
</html>"""
    
    html_report.write_text(html_content, encoding="utf8")
    print(f"📄 Report saved to {html_report}")
    
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())