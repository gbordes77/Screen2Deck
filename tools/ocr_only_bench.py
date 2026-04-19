#!/usr/bin/env python3
"""OCR-only validation harness for Screen2Deck.

Uploads every image under ``validation_set/images/`` to a running
backend, polls each job to completion, then compares the normalized
deck against the ground-truth ``.txt`` files in
``validation_set/truth/`` (when one exists).

Intended to be run in the full-OCR mode (ENABLE_VISION_FALLBACK=false
or VISION_PRIMARY=false without any API key configured) so we can
prove the deterministic OCR pipeline handles the validation set
end-to-end without any LLM in the loop. The harness does NOT care
whether the backend can also reach Gemini/Claude — it only checks
end-to-end behaviour, timing, and card-level accuracy against the
truth files.

Outputs
-------
Two artifacts are written under ``artifacts/reports/ocr_only/``:

1. ``validation.json`` — machine-readable report (per-image + summary)
2. ``validation.md``   — human-readable summary for release notes

Usage
-----
    python tools/ocr_only_bench.py \
        --images validation_set/images \
        --truth  validation_set/truth \
        --url    http://localhost:8080 \
        --out    artifacts/reports/ocr_only
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import requests

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

_QTY_LINE_RX = re.compile(r"^\s*(\d+)\s*[xX]?\s+(.+?)\s*$")


@dataclass
class TruthDeck:
    """Ground-truth deck parsed from a .txt file (MTGA-style)."""

    main: list[tuple[int, str]] = field(default_factory=list)
    side: list[tuple[int, str]] = field(default_factory=list)

    def cards(self) -> list[tuple[int, str, str]]:
        """Flatten to ``[(qty, name, section), ...]``."""
        return [(q, n, "main") for q, n in self.main] + [
            (q, n, "side") for q, n in self.side
        ]


def parse_truth(path: Path) -> TruthDeck:
    deck = TruthDeck()
    section = "main"
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.lower().startswith("sideboard"):
            section = "side"
            continue
        m = _QTY_LINE_RX.match(line)
        if not m:
            continue
        qty = int(m.group(1))
        name = m.group(2).strip()
        (deck.main if section == "main" else deck.side).append((qty, name))
    return deck


def load_truth_for_image(truth_dir: Path, image: Path) -> Optional[TruthDeck]:
    """Look up the truth file for a given image.

    We match by image stem (``MTGA deck list_1535x728.jpeg`` →
    ``MTGA deck list_1535x728.txt``) which is how the provided
    validation_set/truth/ directory is organised.
    """
    candidate = truth_dir / f"{image.stem}.txt"
    if candidate.exists():
        return parse_truth(candidate)
    return None


def _norm(name: str) -> str:
    # Case-fold + collapse whitespace + strip commas / periods for comparison.
    return re.sub(r"\s+", " ", name.lower().replace(",", "").replace(".", "")).strip()


@dataclass
class AccuracyScore:
    truth_total: int
    exact_matches: int
    fuzzy_matches: int

    @property
    def exact_pct(self) -> float:
        return (self.exact_matches / self.truth_total * 100) if self.truth_total else 0.0

    @property
    def fuzzy_pct(self) -> float:
        return (self.fuzzy_matches / self.truth_total * 100) if self.truth_total else 0.0


def score_accuracy(detected_main, detected_side, truth: TruthDeck) -> AccuracyScore:
    """Count how many truth cards were detected (exact + fuzzy >0.88)."""
    detected_flat: list[tuple[int, str]] = [
        (int(c.get("qty", 0) or 0), _norm(c.get("name", "")))
        for section in (detected_main, detected_side)
        for c in section or []
    ]
    exact = 0
    fuzzy = 0
    total = len(truth.main) + len(truth.side)
    for qty, name in [(q, _norm(n)) for q, n in truth.main + truth.side]:
        exact_match = any(dq == qty and dn == name for dq, dn in detected_flat)
        if exact_match:
            exact += 1
            fuzzy += 1
            continue
        fuzzy_match = any(
            dq == qty and difflib.SequenceMatcher(None, dn, name).ratio() >= 0.88
            for dq, dn in detected_flat
        )
        if fuzzy_match:
            fuzzy += 1
    return AccuracyScore(truth_total=total, exact_matches=exact, fuzzy_matches=fuzzy)


@dataclass
class ImageResult:
    image: str
    resolution: str
    job_id: Optional[str] = None
    upload_ms: float = 0.0
    processing_ms: float = 0.0
    total_ms: float = 0.0
    state: str = "unknown"
    cached: bool = False
    main_count: int = 0
    side_count: int = 0
    raw_span_count: int = 0
    raw_mean_conf: float = 0.0
    truth_main_count: int = 0
    truth_side_count: int = 0
    exact_pct: Optional[float] = None
    fuzzy_pct: Optional[float] = None
    error: Optional[str] = None


def upload_image(base_url: str, image: Path, timeout_s: int = 300) -> tuple[str, bool, float]:
    # Screen2Deck's ``POST /api/ocr/upload`` currently runs the OCR
    # pipeline INLINE (main.py::upload_image awaits process_ocr before
    # returning). That means the request body waits until the whole
    # preprocess + EasyOCR + Scryfall round-trip is done, not just the
    # initial job-created response. A 30-60 s timeout is fine once the
    # backend is warm, but on a cold EasyOCR reader or a 4K screenshot
    # we've seen 2-3 min per image — hence the generous default.
    with image.open("rb") as fh:
        start = time.perf_counter()
        resp = requests.post(
            f"{base_url}/api/ocr/upload",
            files={"file": (image.name, fh, "application/octet-stream")},
            timeout=timeout_s,
        )
        elapsed = (time.perf_counter() - start) * 1000
    resp.raise_for_status()
    data = resp.json()
    return data["jobId"], bool(data.get("cached", False)), elapsed


def wait_for_result(base_url: str, job_id: str, timeout_s: int = 300) -> tuple[dict, float]:
    start = time.perf_counter()
    deadline = start + timeout_s
    sleep = 0.5
    while time.perf_counter() < deadline:
        resp = requests.get(f"{base_url}/api/ocr/status/{job_id}", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("state") in {"completed", "failed"}:
            elapsed = (time.perf_counter() - start) * 1000
            return data, elapsed
        time.sleep(sleep)
        sleep = min(sleep + 0.25, 2.0)
    raise TimeoutError(f"job {job_id} did not complete within {timeout_s}s")


def detect_resolution(image: Path) -> str:
    # Image stems encode resolution as ``_WxH`` — cheap enough to parse.
    m = re.search(r"_(\d{3,5})x(\d{3,5})", image.stem)
    return f"{m.group(1)}x{m.group(2)}" if m else "unknown"


def bench_image(base_url: str, image: Path, truth: Optional[TruthDeck]) -> ImageResult:
    result = ImageResult(image=image.name, resolution=detect_resolution(image))
    try:
        # Each upload blocks until the whole OCR pipeline finishes
        # (see main.py::upload_image). On CPU-bound deployments a
        # 4K screenshot with 4 preprocess variants can exceed 20 min,
        # so give each image up to 30 minutes before we give up.
        job_id, cached, upload_ms = upload_image(base_url, image, timeout_s=1800)
        result.job_id = job_id
        result.cached = cached
        result.upload_ms = upload_ms

        status, processing_ms = wait_for_result(base_url, job_id)
        result.processing_ms = processing_ms
        result.total_ms = upload_ms + processing_ms
        result.state = status.get("state", "unknown")

        if result.state == "completed":
            payload = status.get("result") or {}
            normalized = payload.get("normalized") or {}
            raw = payload.get("raw") or {}
            main = normalized.get("main") or []
            side = normalized.get("side") or []
            result.main_count = len(main)
            result.side_count = len(side)
            result.raw_span_count = len(raw.get("spans") or [])
            result.raw_mean_conf = float(raw.get("mean_conf") or 0.0)

            if truth is not None:
                score = score_accuracy(main, side, truth)
                result.truth_main_count = len(truth.main)
                result.truth_side_count = len(truth.side)
                result.exact_pct = round(score.exact_pct, 1)
                result.fuzzy_pct = round(score.fuzzy_pct, 1)
        else:
            result.error = status.get("error") or "job did not complete"
    except Exception as exc:  # noqa: BLE001 — keep harness resilient
        result.error = f"{type(exc).__name__}: {exc}"
        if result.state == "unknown":
            result.state = "error"
    return result


def collect_images(images_dir: Path) -> list[Path]:
    return sorted(p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def backend_env(base_url: str) -> dict:
    env = {}
    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        if resp.ok:
            env["health"] = resp.json()
    except Exception:
        pass
    return env


def summarise(results: list[ImageResult]) -> dict:
    completed = [r for r in results if r.state == "completed"]
    timings = [r.total_ms for r in completed]
    with_truth = [r for r in completed if r.exact_pct is not None]

    def _pct(values, q):
        if not values:
            return 0.0
        values = sorted(values)
        idx = min(len(values) - 1, int(q * len(values)))
        return values[idx]

    return {
        "total": len(results),
        "completed": len(completed),
        "failed": len(results) - len(completed),
        "with_truth": len(with_truth),
        "timings_ms": {
            "mean": round(statistics.mean(timings), 1) if timings else 0,
            "median": round(statistics.median(timings), 1) if timings else 0,
            "p95": round(_pct(timings, 0.95), 1),
            "min": round(min(timings), 1) if timings else 0,
            "max": round(max(timings), 1) if timings else 0,
        },
        "accuracy": {
            "exact_pct_mean": round(
                statistics.mean(r.exact_pct for r in with_truth), 1
            ) if with_truth else None,
            "fuzzy_pct_mean": round(
                statistics.mean(r.fuzzy_pct for r in with_truth), 1
            ) if with_truth else None,
        },
    }


def write_reports(out_dir: Path, report: dict) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "validation.json"
    md_path = out_dir / "validation.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_lines = [
        "# OCR-only validation report",
        "",
        f"- **Date**: {report['timestamp']}",
        f"- **Git SHA**: `{report['git_sha']}`",
        f"- **Backend**: `{report['base_url']}`",
        f"- **Images tested**: {report['summary']['total']}",
        f"- **Completed**: {report['summary']['completed']}",
        f"- **Failed / timed out**: {report['summary']['failed']}",
        "",
        "## Latency (client-side, full round-trip)",
        "",
        f"- mean: **{report['summary']['timings_ms']['mean']} ms**",
        f"- median: **{report['summary']['timings_ms']['median']} ms**",
        f"- p95: **{report['summary']['timings_ms']['p95']} ms**",
        f"- min / max: {report['summary']['timings_ms']['min']} / {report['summary']['timings_ms']['max']} ms",
        "",
    ]

    acc = report["summary"]["accuracy"]
    if acc["exact_pct_mean"] is not None:
        md_lines += [
            "## Accuracy vs truth files",
            "",
            f"- exact-match mean: **{acc['exact_pct_mean']} %**",
            f"- fuzzy-match mean (>=0.88 similarity): **{acc['fuzzy_pct_mean']} %**",
            "",
        ]

    md_lines += [
        "## Per-image results",
        "",
        "| Image | Resolution | State | Total (ms) | Mean conf | Main | Side | Exact % | Fuzzy % |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report["results"]:
        md_lines.append(
            "| {image} | {res} | {state} | {t} | {conf} | {m} | {s} | {ex} | {fz} |".format(
                image=r["image"],
                res=r["resolution"],
                state=r["state"],
                t=int(r["total_ms"]),
                conf=f"{r['raw_mean_conf']:.2f}",
                m=f"{r['main_count']} / {r['truth_main_count']}",
                s=f"{r['side_count']} / {r['truth_side_count']}",
                ex="—" if r["exact_pct"] is None else f"{r['exact_pct']}",
                fz="—" if r["fuzzy_pct"] is None else f"{r['fuzzy_pct']}",
            )
        )

    md_lines += [
        "",
        "## How to reproduce",
        "",
        "```bash",
        "# 1. put the backend in full-OCR mode (no AI calls at all):",
        "ENABLE_VISION_FALLBACK=false docker compose up -d --force-recreate backend",
        "",
        "# 2. once /health returns 200, run the harness:",
        "make bench-ocr-only",
        "# equivalent to:",
        "#   python tools/ocr_only_bench.py \\",
        "#     --images validation_set/images --truth validation_set/truth \\",
        "#     --out artifacts/reports/ocr_only",
        "```",
        "",
        "## Notes",
        "",
        "- This harness is designed to be invoked with the backend running in",
        "  full-OCR mode (`ENABLE_VISION_FALLBACK=false`). Any LLM call at that",
        "  point indicates a misconfigured deployment, not a failure of the",
        "  harness itself.",
        "- `Main` and `Side` columns show `detected / truth`. A `—` in the",
        "  accuracy columns means no truth file was supplied for that image.",
        "- `Mean conf` comes from EasyOCR's post-filter mean span confidence.",
        "- Per-image latency is dominated by EasyOCR on CPU (no GPU in this",
        "  container). Expect roughly 10-30× faster numbers on a CUDA-enabled",
        "  deployment — this is a reproducibility report, not a performance claim.",
        "- The regex parser in `backend/app/main.py::parse_deck_sections` expects",
        "  each OCR span to contain both the quantity and the card name on the",
        "  same line (e.g. `\"4 Lightning Bolt\"`). When a screenshot's layout",
        "  causes EasyOCR to emit the qty and the name as *separate* spans,",
        "  the parser drops both; this shows up as a low `Main` / `Side` count",
        "  even when `Mean conf` is healthy. The AI-backup path exists precisely",
        "  to rescue those layouts — hence `ENABLE_VISION_FALLBACK=true` in the",
        "  canonical deployment.",
    ]
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, default=Path("validation_set/images"))
    parser.add_argument("--truth", type=Path, default=Path("validation_set/truth"))
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--out", type=Path, default=Path("artifacts/reports/ocr_only"))
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Max seconds to wait for each job to finish (default 300s)",
    )
    args = parser.parse_args()

    if not args.images.is_dir():
        print(f"ERROR: images dir not found: {args.images}", file=sys.stderr)
        return 2

    # Health check with retries — EasyOCR model download can block the
    # event loop for several minutes on a cold backend, so a single
    # 5-second attempt isn't reliable. Retry for up to 15 minutes.
    deadline = time.time() + 900
    last_exc: Optional[Exception] = None
    while time.time() < deadline:
        try:
            health = requests.get(f"{args.url}/health", timeout=60)
            if health.ok:
                last_exc = None
                break
            last_exc = RuntimeError(f"/health HTTP {health.status_code}")
        except Exception as exc:
            last_exc = exc
        time.sleep(10)
    if last_exc is not None:
        print(f"ERROR: backend at {args.url} never became healthy: {last_exc}", file=sys.stderr)
        return 2

    images = collect_images(args.images)
    if not images:
        print(f"ERROR: no images found in {args.images}", file=sys.stderr)
        return 2

    print(f"OCR-only bench: {len(images)} images → {args.url}")
    print("-" * 60)

    results: list[ImageResult] = []
    for idx, image in enumerate(images, 1):
        truth = load_truth_for_image(args.truth, image)
        print(f"[{idx:>2}/{len(images)}] {image.name}", flush=True)
        result = bench_image(args.url, image, truth)
        results.append(result)
        summary = (
            f"    → state={result.state} "
            f"total={int(result.total_ms)}ms "
            f"main={result.main_count} side={result.side_count}"
        )
        if result.exact_pct is not None:
            summary += f" exact={result.exact_pct}% fuzzy={result.fuzzy_pct}%"
        if result.error:
            summary += f"  [err: {result.error}]"
        print(summary, flush=True)

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "git_sha": git_sha(),
        "base_url": args.url,
        "backend": backend_env(args.url),
        "images_dir": str(args.images),
        "truth_dir": str(args.truth),
        "summary": summarise(results),
        "results": [asdict(r) for r in results],
    }

    json_path, md_path = write_reports(args.out, report)

    print()
    print("=" * 60)
    print(f"Summary: {report['summary']}")
    print(f"JSON report: {json_path}")
    print(f"MD report:   {md_path}")

    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
