from pydantic import BaseModel
from typing import List, Optional, Literal

class OCRSpan(BaseModel):
    text: str
    conf: float

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
    state: Literal["queued","processing","completed","failed"]
    progress: int = 100
    result: Optional[DeckResult] = None
    error: Optional[ErrorEnvelope] = None