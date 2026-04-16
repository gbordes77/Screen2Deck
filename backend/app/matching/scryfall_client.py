import json
import os
import sqlite3
import time
import threading
import requests
import unicodedata
from typing import List, Dict, Optional
from ..config import get_settings

S = get_settings()

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  lang TEXT,
  faces TEXT,
  data JSON
);
CREATE INDEX IF NOT EXISTS idx_name ON cards(name);
CREATE INDEX IF NOT EXISTS idx_lang ON cards(lang);
"""


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


# Public identity used in the User-Agent header. Scryfall requires a
# descriptive User-Agent since 2024 (https://scryfall.com/blog/user-agent-
# and-accept-header-now-required-on-the-api-225); a generic `python-
# requests/x.y` is rate-limited more aggressively and may be blocked.
SCRYFALL_USER_AGENT = "Screen2Deck/2.3 (+https://github.com/gbordes77/Screen2Deck)"


class Scryfall:
    def __init__(self, db_path=S.SCRYFALL_DB):
        self.db_path = db_path
        try:
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
            with sqlite3.connect(self.db_path) as con:
                con.executescript(SCHEMA)
        except (sqlite3.OperationalError, OSError):
            import tempfile

            self.db_path = os.path.join(tempfile.gettempdir(), "scryfall_cache.sqlite")
            with sqlite3.connect(self.db_path) as con:
                con.executescript(SCHEMA)
        self._last_call = 0.0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": SCRYFALL_USER_AGENT,
                "Accept": "application/json",
            }
        )
        # Cache `all_names` in process memory so that `resolve()` does not
        # re-open the sqlite file and re-scan the cards table on every call.
        # Bust the cache after hydrate_from_bulk.
        self._all_names_cache: Optional[List[str]] = None
        self._cache_lock = threading.Lock()

    # ----- OFFLINE -----
    def hydrate_from_bulk(self, bulk_path=S.SCRYFALL_BULK_PATH):
        if not os.path.exists(bulk_path):
            raise FileNotFoundError(bulk_path)
        with open(bulk_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("DELETE FROM cards")
            for card in data:
                faces = ",".join(
                    [f.get("name", "") for f in card.get("card_faces", [])]
                )
                cur.execute(
                    "INSERT OR REPLACE INTO cards(id,name,lang,faces,data) VALUES(?,?,?,?,?)",
                    (
                        card.get("id"),
                        card.get("name"),
                        card.get("lang", "en"),
                        faces,
                        json.dumps(card),
                    ),
                )
            con.commit()
        with self._cache_lock:
            self._all_names_cache = None

    def all_names(self) -> List[str]:
        if self._all_names_cache is not None:
            return self._all_names_cache
        with self._cache_lock:
            if self._all_names_cache is not None:
                return self._all_names_cache
            with sqlite3.connect(self.db_path) as con:
                cur = con.cursor()
                cur.execute("SELECT name FROM cards WHERE lang='en'")
                self._all_names_cache = [r[0] for r in cur.fetchall()]
            return self._all_names_cache

    def lookup_exact_ci(self, name: str) -> List[Dict]:
        with sqlite3.connect(self.db_path) as con:
            con.create_function(
                "LOWER", 1, lambda x: x.lower() if isinstance(x, str) else x
            )
            cur = con.cursor()
            cur.execute("SELECT data FROM cards WHERE LOWER(name)=LOWER(?)", (name,))
            return [json.loads(r[0]) for r in cur.fetchall()]

    def lookup_by_name(self, name: str) -> List[Dict]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor()
            cur.execute("SELECT data FROM cards WHERE name=?", (name,))
            return [json.loads(r[0]) for r in cur.fetchall()]

    # ----- ONLINE -----
    def _rate(self):
        delta = (time.monotonic() - self._last_call) * 1000.0
        wait_ms = max(0.0, S.SCRYFALL_API_RATE_LIMIT_MS - delta)
        if wait_ms > 0:
            time.sleep(wait_ms / 1000.0)

    def _get(self, url: str, params: dict) -> Optional[dict]:
        if not S.ENABLE_SCRYFALL_ONLINE_FALLBACK:
            return None
        try:
            self._rate()
            r = self._session.get(url, params=params, timeout=S.SCRYFALL_API_TIMEOUT)
            self._last_call = time.monotonic()
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None

    def online_named_fuzzy(self, name: str) -> Optional[Dict]:
        return self._get("https://api.scryfall.com/cards/named", {"fuzzy": name})

    def online_autocomplete(self, q: str, limit: int = 7) -> List[str]:
        j = self._get(
            "https://api.scryfall.com/cards/autocomplete",
            {"q": q, "include_extras": "false"},
        )
        if not j:
            return []
        return j.get("data", [])[:limit]

    # ----- BATCH (POST /cards/collection) -----
    def batch_resolve(self, names: List[str]) -> Dict[str, Dict]:
        """Resolve up to N card names in one or more /cards/collection calls.

        Scryfall's `/cards/collection` endpoint accepts up to 75 identifiers
        per request and returns exact-ish matches (case and accent
        insensitive). This replaces the historical per-card
        `/cards/named?fuzzy=` loop that serialized N × rate-limit-wait
        seconds on the request path.

        The returned dict is keyed by the caller's requested name, so that
        `normalize_deck` can look up each raw OCR name directly regardless
        of whether Scryfall canonicalised it (e.g. `"lightning bolt"` ->
        `"Lightning Bolt"`).

        Cards that Scryfall could not match are silently dropped from the
        result; callers should fall back to `resolve(name)` for the
        remainder so the fuzzy matcher and the online-fuzzy endpoint still
        get a chance.
        """
        if not names or not S.ENABLE_SCRYFALL_ONLINE_FALLBACK:
            return {}

        out: Dict[str, Dict] = {}

        # Dedupe while preserving order so the mapping is stable.
        seen: set[str] = set()
        unique_requests: List[str] = []
        for n in names:
            key = _fold(n)
            if key and key not in seen:
                seen.add(key)
                unique_requests.append(n)

        for start in range(0, len(unique_requests), 75):
            chunk = unique_requests[start : start + 75]
            identifiers = [{"name": n} for n in chunk]
            try:
                self._rate()
                r = self._session.post(
                    "https://api.scryfall.com/cards/collection",
                    json={"identifiers": identifiers},
                    timeout=S.SCRYFALL_API_TIMEOUT * 2,
                )
                self._last_call = time.monotonic()
                if r.status_code != 200:
                    continue
                data = r.json()
            except Exception:
                continue

            # Map each returned card back to the requested name by folding
            # both sides. Scryfall's matching is already loose on
            # case/spacing/accents so _fold gives us a stable key.
            folded_to_requested: Dict[str, str] = {_fold(req): req for req in chunk}
            for card in data.get("data", []):
                folded = _fold(card.get("name", ""))
                if folded in folded_to_requested:
                    out[folded_to_requested[folded]] = card
                    continue
                # Split/DFC cards: Scryfall returns the composite name
                # (`Fire // Ice`), but OCR may have caught only one face.
                for face in card.get("card_faces", []) or []:
                    face_folded = _fold(face.get("name", ""))
                    if face_folded in folded_to_requested:
                        out[folded_to_requested[face_folded]] = card
                        break

        return out

    # ----- Resolver (toujours appelée) -----
    def resolve(self, raw_name: str, topk: int = 5) -> Dict:
        # 1) Offline exact
        ex = self.lookup_exact_ci(raw_name)
        if ex:
            return {
                "name": ex[0]["name"],
                "id": ex[0].get("id"),
                "source": "offline_exact",
                "candidates": [],
            }
        # 2) Offline fuzzy
        try:
            from rapidfuzz import process, fuzz

            corpus = self.all_names()
            if corpus:
                best = process.extractOne(raw_name, corpus, scorer=fuzz.WRatio)
                cands = process.extract(
                    raw_name, corpus, scorer=fuzz.WRatio, limit=topk
                )
                pack = []
                for cand, sc, _ in cands or []:
                    m = self.lookup_by_name(cand)
                    cid = m[0]["id"] if m else None
                    pack.append({"name": cand, "score": float(sc), "id": cid})
                if best and best[1] >= 85:
                    m = self.lookup_by_name(best[0])
                    if m:
                        return {
                            "name": m[0]["name"],
                            "id": m[0].get("id"),
                            "source": "offline_fuzzy",
                            "candidates": pack,
                        }
        except Exception:
            pass
        # 3) Online fuzzy
        j = self.online_named_fuzzy(raw_name)
        if j and "name" in j:
            return {
                "name": j["name"],
                "id": j.get("id"),
                "source": "online_fuzzy",
                "candidates": [],
            }
        # 4) Online autocomplete -> suggestions
        sugg = self.online_autocomplete(raw_name, limit=topk)
        pack = []
        for cand in sugg:
            m = self.lookup_exact_ci(cand)
            cid = m[0]["id"] if m else None
            pack.append({"name": cand, "score": 0.0, "id": cid})
        # 5) Fallback brut
        return {"name": raw_name, "id": None, "source": "raw", "candidates": pack}


SCRYFALL = Scryfall()
