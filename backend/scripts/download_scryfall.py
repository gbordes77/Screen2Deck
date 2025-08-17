import json, requests, os
from app.config import get_settings
from app.matching.scryfall_client import Scryfall
S = get_settings()
BULK_URL = "https://api.scryfall.com/bulk-data"
def main():
    r = requests.get(BULK_URL, timeout=S.SCRYFALL_TIMEOUT); r.raise_for_status()
    default = next(x for x in r.json()["data"] if x["type"]=="default_cards")
    dl = requests.get(default["download_uri"], timeout=60); dl.raise_for_status()
    os.makedirs(os.path.dirname(S.SCRYFALL_BULK_PATH), exist_ok=True)
    with open(S.SCRYFALL_BULK_PATH, "wb") as f: f.write(dl.content)
    Scryfall().hydrate_from_bulk(S.SCRYFALL_BULK_PATH)
    print("Scryfall cache ready at", S.SCRYFALL_DB)
if __name__ == "__main__": main()