"""Download the Scryfall bulk data file and hydrate the offline cache.

Usable from the repo root (`python backend/scripts/download_scryfall.py`),
from `backend/` (`python scripts/download_scryfall.py`), or via a
module path (`python -m scripts.download_scryfall`). Adds the project
root to ``sys.path`` so `from app...` imports resolve regardless of
the invocation directory.

The `--minimal` flag is accepted for CI compatibility but is currently
a no-op — Scryfall no longer exposes a "minimal" bulk variant, we just
download `default_cards` (≈150 MB compressed).
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Make the `app` package importable regardless of the working directory.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import requests  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.matching.scryfall_client import Scryfall  # noqa: E402

S = get_settings()
BULK_URL = "https://api.scryfall.com/bulk-data"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--minimal",
        action="store_true",
        help="Accepted for CI compatibility; currently a no-op.",
    )
    parser.parse_args()

    headers = {
        "User-Agent": "Screen2Deck/2.4 (+https://github.com/gbordes77/Screen2Deck)",
        "Accept": "application/json",
    }

    print(f"Fetching Scryfall bulk manifest from {BULK_URL}...")
    r = requests.get(BULK_URL, headers=headers, timeout=S.SCRYFALL_TIMEOUT)
    r.raise_for_status()
    default = next(x for x in r.json()["data"] if x["type"] == "default_cards")
    print(f"Downloading {default['download_uri']} ({default.get('size', '?')} bytes)...")

    dl = requests.get(default["download_uri"], headers=headers, timeout=120)
    dl.raise_for_status()

    os.makedirs(os.path.dirname(S.SCRYFALL_BULK_PATH), exist_ok=True)
    with open(S.SCRYFALL_BULK_PATH, "wb") as f:
        f.write(dl.content)
    print(f"Wrote {len(dl.content)} bytes to {S.SCRYFALL_BULK_PATH}")

    Scryfall().hydrate_from_bulk(S.SCRYFALL_BULK_PATH)
    print(f"Scryfall cache ready at {S.SCRYFALL_DB}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
