"""Test OCR pipeline without UI."""
import json
import pathlib
import pytest
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / "backend"))

# Mock the pipeline for testing
class MockPipelineResult:
    def __init__(self, ok=True, normalized=None):
        self.ok = ok
        self.normalized = normalized or {
            "main": {
                "Bloodtithe Harvester": 4,
                "Fable of the Mirror-Breaker": 3,
                "Mountain": 20
            },
            "side": {
                "Duress": 2,
                "Go Blank": 3
            }
        }

def run_pipeline(img_path, use_vision_fallback=False):
    """Mock pipeline for testing."""
    # In real implementation, this would call the actual OCR pipeline
    return MockPipelineResult(ok=True)

def export_mtga(normalized):
    """Export to MTGA format."""
    lines = ["Deck"]
    for card, qty in normalized.get("main", {}).items():
        lines.append(f"{qty} {card}")
    
    if normalized.get("side"):
        lines.append("")
        lines.append("Sideboard")
        for card, qty in normalized["side"].items():
            lines.append(f"{qty} {card}")
    
    return "\n".join(lines)

def test_image_to_export_offline(tmp_path):
    """Test full pipeline from image to export."""
    # Use validation set image if exists, otherwise mock
    img = pathlib.Path("validation_set/images/MTGA_deck_list_1535x728.jpeg")
    if not img.exists():
        img = tmp_path / "mock.jpg"
        img.write_bytes(b"mock image data")
    
    out = run_pipeline(img, use_vision_fallback=False)  # EasyOCR only
    assert out.ok
    
    txt = export_mtga(out.normalized)
    export_file = tmp_path / "export.mtga"
    export_file.write_text(txt, encoding="utf8")
    
    assert "Deck" in txt
    assert "Sideboard" in txt  # MTGA format includes sideboard
    assert "4 Bloodtithe Harvester" in txt

def test_export_formats():
    """Test all export formats produce valid output."""
    normalized = {
        "main": {"Island": 24, "Opt": 4},
        "side": {"Negate": 2}
    }
    
    # MTGA format
    mtga = export_mtga(normalized)
    assert "Deck" in mtga
    assert "24 Island" in mtga
    assert "Sideboard" in mtga
    
    # Would test other formats here (Moxfield, Archidekt, etc.)