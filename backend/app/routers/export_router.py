"""
Export endpoints for Screen2Deck API.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List

from ..models import NormalizedDeck, NormalizedCard
from ..exporters.mtga import export_mtga
from ..exporters.moxfield import export_moxfield
from ..exporters.archidekt import export_archidekt
from ..exporters.tappedout import export_tappedout
from ..telemetry import logger, telemetry

router = APIRouter()

class CardIn(BaseModel):
    qty: int
    name: str
    scryfall_id: Optional[str] = None

class ExportPayload(BaseModel):
    main: List[CardIn]
    side: List[CardIn] = []

def _to_normalized(payload: ExportPayload) -> NormalizedDeck:
    main = [NormalizedCard(qty=c.qty, name=c.name, scryfall_id=c.scryfall_id) for c in payload.main]
    side = [NormalizedCard(qty=c.qty, name=c.name, scryfall_id=c.scryfall_id) for c in payload.side]
    return NormalizedDeck(main=main, side=side)

@router.post(
    "/{format}",
    response_class=PlainTextResponse,
    summary="Export deck to format",
    description="Export a normalized deck to specified format (unauthenticated for CI golden tests)"
)
async def export_deck(format: str, payload: ExportPayload):
    """
    Export a deck to the specified format.
    """
    # Simple format validation
    valid_formats = ["mtga", "moxfield", "archidekt", "tappedout"]
    if format not in valid_formats:
        raise HTTPException(status_code=400, detail="Invalid export format")
    
    deck = _to_normalized(payload)
    
    with telemetry.span("export_deck") as span:
        try:
            if format == "mtga":
                return export_mtga(deck)
            if format == "moxfield":
                return export_moxfield(deck)
            if format == "archidekt":
                return export_archidekt(deck)
            if format == "tappedout":
                return export_tappedout(deck)
            raise HTTPException(status_code=400, detail="Unknown export format")
        except Exception as e:
            telemetry.record_exception(e, {"format": format})
            logger.exception("export_failed")
            # Return clean 500
            raise HTTPException(status_code=500, detail="export_failed")


@router.get(
    "/formats",
    summary="List export formats",
    description="Get list of supported export formats"
)
async def list_formats():
    """
    List all supported export formats.
    """
    return {
        "formats": [
            {
                "id": "mtga",
                "name": "MTG Arena",
                "description": "MTG Arena deck format",
                "example": "4 Lightning Bolt (2XM) 129"
            },
            {
                "id": "moxfield",
                "name": "Moxfield",
                "description": "Moxfield deck format",
                "example": "4 Lightning Bolt"
            },
            {
                "id": "archidekt",
                "name": "Archidekt",
                "description": "Archidekt deck format",
                "example": "// Main\\n4 Lightning Bolt"
            },
            {
                "id": "tappedout",
                "name": "TappedOut",
                "description": "TappedOut deck format",
                "example": "4x Lightning Bolt"
            },
            {
                "id": "json",
                "name": "JSON",
                "description": "Raw JSON format",
                "example": '{"main": [...], "side": [...]}'
            }
        ]
    }


from pydantic import BaseModel