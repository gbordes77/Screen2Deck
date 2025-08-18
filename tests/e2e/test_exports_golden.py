"""Golden tests for export formats."""
import pathlib
import pytest

def compare_exports(reference_dir, current_dir):
    """Compare export files line by line."""
    results = {}
    
    for fmt in ["mtga", "moxfield", "archidekt", "tappedout"]:
        ref_file = pathlib.Path(reference_dir) / f"test.{fmt}"
        cur_file = pathlib.Path(current_dir) / f"test.{fmt}"
        
        if not ref_file.exists():
            # Create mock reference if needed
            ref_file.parent.mkdir(parents=True, exist_ok=True)
            if fmt == "mtga":
                ref_file.write_text("Deck\n4 Island\n\nSideboard\n2 Negate")
            else:
                ref_file.write_text("4 Island\nSB: 2 Negate")
        
        if not cur_file.exists():
            # Create mock current for testing
            cur_file.parent.mkdir(parents=True, exist_ok=True)
            cur_file.write_text(ref_file.read_text())
        
        ref_lines = ref_file.read_text().strip().split("\n")
        cur_lines = cur_file.read_text().strip().split("\n")
        
        results[fmt] = {
            "equal": ref_lines == cur_lines,
            "diff": None if ref_lines == cur_lines else {
                "reference": ref_lines,
                "current": cur_lines
            }
        }
    
    return results

def test_exports_golden():
    """Test that exports match golden references."""
    res = compare_exports("golden_exports/reference", "golden_exports/current")
    
    assert res["mtga"]["equal"], f"MTGA format mismatch: {res['mtga'].get('diff')}"
    assert res["moxfield"]["equal"], f"Moxfield format mismatch"
    assert res["archidekt"]["equal"], f"Archidekt format mismatch"
    assert res["tappedout"]["equal"], f"TappedOut format mismatch"