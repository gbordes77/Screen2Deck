"""Test deck list parsing."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

def parse_line(line: str) -> tuple:
    """Parse a deck list line."""
    line = line.strip()
    if not line:
        return None
    
    # Check for sideboard marker
    if line.startswith("SB:"):
        line = line[3:].strip()
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            return ("SB", int(parts[0]), parts[1])
    
    # Normal main deck line
    parts = line.split(None, 1)
    if len(parts) == 2 and parts[0].isdigit():
        return (int(parts[0]), parts[1])
    
    return None

def test_parse_qty_name():
    assert parse_line("4 Bloodtithe Harvester") == (4, "Bloodtithe Harvester")
    assert parse_line("1 Island") == (1, "Island")
    assert parse_line("SB: 2 Duress") == ("SB", 2, "Duress")
    assert parse_line("SB: 3 Go Blank") == ("SB", 3, "Go Blank")

def test_parse_empty_invalid():
    assert parse_line("") is None
    assert parse_line("Not a valid line") is None
    assert parse_line("Island") is None  # No quantity