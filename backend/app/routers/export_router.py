"""
Export endpoints for Screen2Deck API.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Optional

from ..models import NormalizedDeck
from ..core.validation import text_validator
from ..auth import TokenData, require_permission
from ..telemetry import logger
from ..error_taxonomy import EXPORT_INVALID
from .metrics import record_export_request

# Import exporters
from ..exporters.mtga import export_mtga
from ..exporters.moxfield import export_moxfield
from ..exporters.archidekt import export_archidekt
from ..exporters.tappedout import export_tappedout

router = APIRouter()

class ExportRequest(BaseModel):
    deck: NormalizedDeck
    format: str

class ExportResponse(BaseModel):
    text: str
    format: str


@router.post(
    "/{format}",
    response_model=ExportResponse,
    summary="Export deck to format",
    description="Export a normalized deck to specified format",
    dependencies=[Depends(require_permission("export:read"))]
)
async def export_deck(
    format: str,
    deck: NormalizedDeck,
    token_data: TokenData = Depends(require_permission("export:read"))
):
    """
    Export a deck to the specified format.
    
    Supported formats:
    - mtga: MTG Arena
    - moxfield: Moxfield
    - archidekt: Archidekt
    - tappedout: TappedOut
    - json: Raw JSON
    """
    # Validate format
    if not text_validator.validate_export_format(format):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": EXPORT_INVALID,
                "message": f"Unknown export format: {format}"
            }
        )
    
    # Export based on format
    try:
        if format == "mtga":
            text = export_mtga(deck)
        elif format == "moxfield":
            text = export_moxfield(deck)
        elif format == "archidekt":
            text = export_archidekt(deck)
        elif format == "tappedout":
            text = export_tappedout(deck)
        elif format == "json":
            import json
            text = json.dumps(deck.model_dump(), indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # Record metric
        record_export_request(format)
        
        logger.info(f"Exported deck to {format} format")
        
        return ExportResponse(text=text, format=format)
        
    except Exception as e:
        logger.error(f"Export failed for format {format}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": EXPORT_INVALID,
                "message": f"Export failed: {str(e)}"
            }
        )


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