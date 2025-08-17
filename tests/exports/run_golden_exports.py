#!/usr/bin/env python3
import argparse, difflib, json, os, sys, time
from pathlib import Path
import urllib.request

BASE = os.environ.get("EXPORT_BASE_URL", "http://localhost:8080")
TARGETS = ["mtga", "moxfield", "archidekt", "tappedout"]

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "input" / "deck_normalized.json"
GOLDENS = ROOT / "goldens"

def post_export(target: str, payload: dict, timeout=60) -> str:
    url = f"{BASE}/api/export/{target}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return body

def normalize(txt: str) -> str:
    # uniformiser fin de ligne et supprimer espaces fin de ligne
    lines = [line.rstrip() for line in txt.replace("\r\n","\n").replace("\r","\n").split("\n")]
    # option: supprimer lignes vides en fin de fichier
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"

def main(update: bool=False) -> int:
    with open(INPUT, "r", encoding="utf-8") as f:
        deck = json.load(f)

    failures = 0
    OUTDIR = ROOT / "output"
    OUTDIR.mkdir(parents=True, exist_ok=True)
    
    for target in TARGETS:
        print(f"==> {target}")
        try:
            out = normalize(post_export(target, deck))
            # Always save output for debugging
            (OUTDIR / f"{target}.txt").write_text(out, encoding="utf-8")
        except Exception as e:
            print(f"  ❌ Failed to export {target}: {e}")
            failures += 1
            continue
            
        golden_file = GOLDENS / f"{target}.txt"

        if update or not golden_file.exists():
            golden_file.parent.mkdir(parents=True, exist_ok=True)
            golden_file.write_text(out, encoding="utf-8")
            print(f"  [updated] {golden_file}")
            continue

        expected = normalize(golden_file.read_text(encoding="utf-8"))

        if out != expected:
            print(f"  ❌ mismatch for {target}")
            diff = difflib.unified_diff(
                expected.splitlines(keepends=True),
                out.splitlines(keepends=True),
                fromfile=f"goldens/{target}.txt",
                tofile=f"output/{target}.txt"
            )
            sys.stdout.writelines(diff)
            failures += 1
        else:
            print(f"  ✅ match")

    return 1 if failures else 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="overwrite goldens with current exporter output")
    args = ap.parse_args()
    rc = main(update=args.update)
    sys.exit(rc)