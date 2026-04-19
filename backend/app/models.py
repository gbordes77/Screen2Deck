from pydantic import BaseModel
from typing import List, Optional, Literal


class OCRSpan(BaseModel):
    text: str
    conf: float
    # EasyOCR ``readtext(detail=1)`` returns a 4-corner polygon per
    # span. We keep it as ``[[x, y], [x, y], [x, y], [x, y]]`` so the
    # spatial parser in ``main.py::parse_deck_sections`` can pair a
    # right-column quantity span (e.g. ``"x2"``) with the left-column
    # card-name span that sits on the same row. ``None`` when the
    # spans are synthesised (e.g. by the Vision-LLM fallback, which
    # already returns a structured deck and has no OCR geometry).
    bbox: Optional[List[List[float]]] = None


class RawOCR(BaseModel):
    spans: List[OCRSpan]
    mean_conf: float


class CardCandidate(BaseModel):
    name: str
    score: float
    scryfall_id: Optional[str] = None


class CardEntry(BaseModel):
    qty: int
    name: str
    candidates: List[CardCandidate] = []


class DeckSections(BaseModel):
    main: List[CardEntry]
    side: List[CardEntry]


class NormalizedCard(BaseModel):
    qty: int
    name: str
    scryfall_id: Optional[str]


class NormalizedDeck(BaseModel):
    main: List[NormalizedCard]
    side: List[NormalizedCard]


class DeckResult(BaseModel):
    jobId: str
    raw: RawOCR
    parsed: DeckSections
    normalized: NormalizedDeck
    timings_ms: dict
    traceId: str


class ErrorEnvelope(BaseModel):
    code: str
    message: str


class UploadResponse(BaseModel):
    jobId: str


class StatusResponse(BaseModel):
    state: Literal["queued", "processing", "completed", "failed"]
    progress: int = 100
    result: Optional[DeckResult] = None
    error: Optional[ErrorEnvelope] = None
