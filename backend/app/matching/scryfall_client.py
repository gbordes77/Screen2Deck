import json, os, sqlite3, time, requests, unicodedata
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
"""

def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())

class Scryfall:
    def __init__(self, db_path=S.SCRYFALL_DB):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as con:
            con.executescript(SCHEMA)
        self._last_call = 0.0
        self._session = requests.Session()

    # ----- OFFLINE -----
    def hydrate_from_bulk(self, bulk_path=S.SCRYFALL_BULK_PATH):
        if not os.path.exists(bulk_path): raise FileNotFoundError(bulk_path)
        with open(bulk_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor(); cur.execute("DELETE FROM cards")
            for card in data:
                faces = ",".join([f.get("name","") for f in card.get("card_faces",[])])
                cur.execute("INSERT OR REPLACE INTO cards(id,name,lang,faces,data) VALUES(?,?,?,?,?)",
                            (card.get("id"), card.get("name"), card.get("lang","en"), faces, json.dumps(card)))
            con.commit()

    def all_names(self) -> List[str]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor(); cur.execute("SELECT name FROM cards WHERE lang='en'")
            return [r[0] for r in cur.fetchall()]

    def lookup_exact_ci(self, name: str) -> List[Dict]:
        with sqlite3.connect(self.db_path) as con:
            con.create_function("LOWER", 1, lambda x: x.lower() if isinstance(x,str) else x)
            cur = con.cursor(); cur.execute("SELECT data FROM cards WHERE LOWER(name)=LOWER(?)", (name,))
            return [json.loads(r[0]) for r in cur.fetchall()]

    def lookup_by_name(self, name: str) -> List[Dict]:
        with sqlite3.connect(self.db_path) as con:
            cur = con.cursor(); cur.execute("SELECT data FROM cards WHERE name=?", (name,))
            return [json.loads(r[0]) for r in cur.fetchall()]

    # ----- ONLINE -----
    def _rate(self):
        delta = (time.monotonic() - self._last_call) * 1000.0
        wait_ms = max(0.0, S.SCRYFALL_API_RATE_LIMIT_MS - delta)
        if wait_ms > 0: time.sleep(wait_ms/1000.0)

    def _get(self, url: str, params: dict) -> Optional[dict]:
        if not S.ENABLE_SCRYFALL_ONLINE_FALLBACK: return None
        try:
            self._rate()
            r = self._session.get(url, params=params, timeout=S.SCRYFALL_API_TIMEOUT)
            self._last_call = time.monotonic()
            if r.status_code != 200: return None
            return r.json()
        except Exception:
            return None

    def online_named_fuzzy(self, name: str) -> Optional[Dict]:
        return self._get("https://api.scryfall.com/cards/named", {"fuzzy": name})

    def online_autocomplete(self, q: str, limit: int=7) -> List[str]:
        j = self._get("https://api.scryfall.com/cards/autocomplete", {"q": q, "include_extras": "false"})
        if not j: return []
        return j.get("data", [])[:limit]

    # ----- Resolver (toujours appelée) -----
    def resolve(self, raw_name: str, topk: int=5) -> Dict:
        # 1) Offline exact
        ex = self.lookup_exact_ci(raw_name)
        if ex:
            return {"name": ex[0]["name"], "id": ex[0].get("id"), "source": "offline_exact", "candidates": []}
        # 2) Offline fuzzy
        try:
            from rapidfuzz import process, fuzz
            corpus = self.all_names()
            if corpus:
                best = process.extractOne(raw_name, corpus, scorer=fuzz.WRatio)
                cands = process.extract(raw_name, corpus, scorer=fuzz.WRatio, limit=topk)
                pack = []
                for cand, sc, _ in (cands or []):
                    m = self.lookup_by_name(cand); cid = m[0]["id"] if m else None
                    pack.append({"name": cand, "score": float(sc), "id": cid})
                if best and best[1] >= 85:
                    m = self.lookup_by_name(best[0])
                    if m:
                        return {"name": m[0]["name"], "id": m[0].get("id"), "source": "offline_fuzzy", "candidates": pack}
        except Exception:
            pass
        # 3) Online fuzzy
        j = self.online_named_fuzzy(raw_name)
        if j and "name" in j:
            return {"name": j["name"], "id": j.get("id"), "source": "online_fuzzy", "candidates": []}
        # 4) Online autocomplete -> suggestions
        sugg = self.online_autocomplete(raw_name, limit=topk)
        pack = []
        for cand in sugg:
            m = self.lookup_exact_ci(cand); cid = m[0]["id"] if m else None
            pack.append({"name": cand, "score": 0.0, "id": cid})
        # 5) Fallback brut
        return {"name": raw_name, "id": None, "source": "raw", "candidates": pack}

SCRYFALL = Scryfall()