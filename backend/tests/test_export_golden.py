"""
Golden tests for export formats
Ensures export format consistency and correctness
"""

import pytest
import json
from pathlib import Path
from typing import Dict

from app.exporters.mtga import MTGAExporter
from app.exporters.moxfield import MoxfieldExporter
from app.exporters.archidekt import ArchidektExporter
from app.exporters.tappedout import TappedOutExporter

# Sample deck for testing
SAMPLE_DECK = {
    "main": [
        {"qty": 4, "name": "Lightning Bolt", "scryfall_id": "a57af4df-566c-4c65-9cfe-31a96f8e4e3f", "set": "2xm", "collector_number": "129"},
        {"qty": 4, "name": "Counterspell", "scryfall_id": "ce30f926-bc06-46ee-9f35-26e4d7e2a5c8", "set": "mh2", "collector_number": "267"},
        {"qty": 2, "name": "Teferi, Time Raveler", "scryfall_id": "5cb76266-ae50-4bbc-8f96-d98f309b02d3", "set": "war", "collector_number": "221"},
        {"qty": 24, "name": "Island", "scryfall_id": "b2a5b0a9-b8a4-4c4e-8c9e-3c3c3c3c3c3c", "set": "xln", "collector_number": "265"},
        {"qty": 26, "name": "Mountain", "scryfall_id": "c3c3c3c3-c3c3-4c4e-8c9e-b2a5b0a9b8a4", "set": "xln", "collector_number": "273"}
    ],
    "side": [
        {"qty": 3, "name": "Surgical Extraction", "scryfall_id": "6e438caf-ef4f-4ab2-ae82-c2e6c5e5e5e5", "set": "nph", "collector_number": "74"},
        {"qty": 2, "name": "Damping Sphere", "scryfall_id": "a5b0b0a9-b8a4-4c4e-8c9e-d3d3d3d3d3d3", "set": "dom", "collector_number": "213"},
        {"qty": 2, "name": "Pyroblast", "scryfall_id": "b029eb9a-dd7a-40c2-96c4-0063d9cc002c", "set": "ice", "collector_number": "213"},
        {"qty": 4, "name": "Relic of Progenitus", "scryfall_id": "436cd66c-0622-43cd-8748-af4d21a2db3f", "set": "ema", "collector_number": "231"},
        {"qty": 4, "name": "Blood Moon", "scryfall_id": "d50988ad-a7dc-4ae3-bdd7-c4d6d3789bf2", "set": "a25", "collector_number": "122"}
    ]
}

# Golden outputs for each format
GOLDEN_MTGA = """Deck
4 Lightning Bolt (2XM) 129
4 Counterspell (MH2) 267
2 Teferi, Time Raveler (WAR) 221
24 Island (XLN) 265
26 Mountain (XLN) 273

Sideboard
3 Surgical Extraction (NPH) 74
2 Damping Sphere (DOM) 213
2 Pyroblast (ICE) 213
4 Relic of Progenitus (EMA) 231
4 Blood Moon (A25) 122"""

GOLDEN_MOXFIELD = """4 Lightning Bolt
4 Counterspell
2 Teferi, Time Raveler
24 Island
26 Mountain

Sideboard:
3 Surgical Extraction
2 Damping Sphere
2 Pyroblast
4 Relic of Progenitus
4 Blood Moon"""

GOLDEN_ARCHIDEKT = """// Main
4 Lightning Bolt
4 Counterspell
2 Teferi, Time Raveler
24 Island
26 Mountain

// Sideboard
3 Surgical Extraction
2 Damping Sphere
2 Pyroblast
4 Relic of Progenitus
4 Blood Moon"""

GOLDEN_TAPPEDOUT = """4x Lightning Bolt
4x Counterspell
2x Teferi, Time Raveler
24x Island
26x Mountain

Sideboard:
3x Surgical Extraction
2x Damping Sphere
2x Pyroblast
4x Relic of Progenitus
4x Blood Moon"""

class TestExportGolden:
    """Test export formats against golden outputs"""
    
    def test_mtga_export(self):
        """Test MTGA format export"""
        exporter = MTGAExporter()
        result = exporter.export(SAMPLE_DECK)
        
        # Normalize line endings for comparison
        result_lines = result.strip().split('\n')
        golden_lines = GOLDEN_MTGA.strip().split('\n')
        
        assert len(result_lines) == len(golden_lines), f"Line count mismatch: {len(result_lines)} vs {len(golden_lines)}"
        
        for i, (result_line, golden_line) in enumerate(zip(result_lines, golden_lines)):
            assert result_line.strip() == golden_line.strip(), f"Line {i+1} mismatch:\nGot: {result_line}\nExpected: {golden_line}"
    
    def test_moxfield_export(self):
        """Test Moxfield format export"""
        exporter = MoxfieldExporter()
        result = exporter.export(SAMPLE_DECK)
        
        result_lines = result.strip().split('\n')
        golden_lines = GOLDEN_MOXFIELD.strip().split('\n')
        
        assert len(result_lines) == len(golden_lines), f"Line count mismatch: {len(result_lines)} vs {len(golden_lines)}"
        
        for i, (result_line, golden_line) in enumerate(zip(result_lines, golden_lines)):
            assert result_line.strip() == golden_line.strip(), f"Line {i+1} mismatch:\nGot: {result_line}\nExpected: {golden_line}"
    
    def test_archidekt_export(self):
        """Test Archidekt format export"""
        exporter = ArchidektExporter()
        result = exporter.export(SAMPLE_DECK)
        
        result_lines = result.strip().split('\n')
        golden_lines = GOLDEN_ARCHIDEKT.strip().split('\n')
        
        assert len(result_lines) == len(golden_lines), f"Line count mismatch: {len(result_lines)} vs {len(golden_lines)}"
        
        for i, (result_line, golden_line) in enumerate(zip(result_lines, golden_lines)):
            assert result_line.strip() == golden_line.strip(), f"Line {i+1} mismatch:\nGot: {result_line}\nExpected: {golden_line}"
    
    def test_tappedout_export(self):
        """Test TappedOut format export"""
        exporter = TappedOutExporter()
        result = exporter.export(SAMPLE_DECK)
        
        result_lines = result.strip().split('\n')
        golden_lines = GOLDEN_TAPPEDOUT.strip().split('\n')
        
        assert len(result_lines) == len(golden_lines), f"Line count mismatch: {len(result_lines)} vs {len(golden_lines)}"
        
        for i, (result_line, golden_line) in enumerate(zip(result_lines, golden_lines)):
            assert result_line.strip() == golden_line.strip(), f"Line {i+1} mismatch:\nGot: {result_line}\nExpected: {golden_line}"
    
    def test_export_consistency(self):
        """Test that all formats export the same cards"""
        exporters = {
            'mtga': MTGAExporter(),
            'moxfield': MoxfieldExporter(),
            'archidekt': ArchidektExporter(),
            'tappedout': TappedOutExporter()
        }
        
        # Extract card counts from each export
        card_counts = {}
        
        for format_name, exporter in exporters.items():
            result = exporter.export(SAMPLE_DECK)
            counts = {}
            
            # Parse the export to count cards
            for line in result.split('\n'):
                line = line.strip()
                if not line or line.startswith('//') or line.endswith(':'):
                    continue
                
                # Extract quantity and name
                if format_name == 'mtga':
                    # Format: "4 Lightning Bolt (SET) NUM"
                    parts = line.split(' (')
                    if len(parts) >= 1:
                        qty_name = parts[0]
                        if ' ' in qty_name:
                            qty, name = qty_name.split(' ', 1)
                            counts[name] = int(qty)
                
                elif format_name == 'tappedout':
                    # Format: "4x Lightning Bolt"
                    if 'x ' in line:
                        qty, name = line.split('x ', 1)
                        counts[name] = int(qty)
                
                else:
                    # Format: "4 Lightning Bolt"
                    if ' ' in line:
                        parts = line.split(' ', 1)
                        if parts[0].isdigit():
                            counts[parts[1]] = int(parts[0])
            
            card_counts[format_name] = counts
        
        # Verify all formats have same cards
        first_format = list(card_counts.keys())[0]
        base_counts = card_counts[first_format]
        
        for format_name, counts in card_counts.items():
            if format_name == first_format:
                continue
            
            # Check same cards are present
            assert set(counts.keys()) == set(base_counts.keys()), \
                f"{format_name} has different cards than {first_format}"
            
            # Check same quantities
            for card, qty in counts.items():
                assert qty == base_counts[card], \
                    f"{format_name} has {qty} {card}, but {first_format} has {base_counts[card]}"
    
    def test_special_cards_handling(self):
        """Test handling of special card types"""
        special_deck = {
            "main": [
                # Double-faced card
                {"qty": 2, "name": "Delver of Secrets // Insectile Aberration", "scryfall_id": "test1"},
                # Split card
                {"qty": 3, "name": "Fire // Ice", "scryfall_id": "test2"},
                # Adventure card
                {"qty": 4, "name": "Bonecrusher Giant", "scryfall_id": "test3"},
                # Card with apostrophe
                {"qty": 1, "name": "Urza's Saga", "scryfall_id": "test4"},
                # Card with comma
                {"qty": 1, "name": "Borborygmos, Enraged", "scryfall_id": "test5"}
            ],
            "side": []
        }
        
        # Test each exporter handles special cards
        exporters = [
            MTGAExporter(),
            MoxfieldExporter(),
            ArchidektExporter(),
            TappedOutExporter()
        ]
        
        for exporter in exporters:
            result = exporter.export(special_deck)
            
            # Verify all cards are present
            assert "Delver of Secrets" in result or "Insectile Aberration" in result
            assert "Fire" in result or "Ice" in result
            assert "Bonecrusher Giant" in result
            assert "Urza" in result
            assert "Borborygmos" in result
    
    @pytest.mark.parametrize("deck_size,expected_main,expected_side", [
        ({"main": [{"qty": 60, "name": "Island"}], "side": []}, 60, 0),
        ({"main": [{"qty": 40, "name": "Island"}], "side": []}, 40, 0),  # Limited
        ({"main": [{"qty": 60, "name": "Island"}], "side": [{"qty": 15, "name": "Mountain"}]}, 60, 15),
        ({"main": [{"qty": 100, "name": "Island"}], "side": []}, 100, 0),  # Commander
    ])
    def test_deck_sizes(self, deck_size, expected_main, expected_side):
        """Test various deck sizes are handled correctly"""
        exporter = MTGAExporter()
        result = exporter.export(deck_size)
        
        # Count cards in result
        main_count = 0
        side_count = 0
        in_sideboard = False
        
        for line in result.split('\n'):
            if 'Sideboard' in line:
                in_sideboard = True
                continue
            
            if line.strip() and not line.startswith('Deck'):
                parts = line.strip().split(' ', 1)
                if parts[0].isdigit():
                    qty = int(parts[0])
                    if in_sideboard:
                        side_count += qty
                    else:
                        main_count += qty
        
        assert main_count == expected_main, f"Main deck size mismatch: {main_count} vs {expected_main}"
        assert side_count == expected_side, f"Sideboard size mismatch: {side_count} vs {expected_side}"

@pytest.fixture
def golden_dir(tmp_path):
    """Create temporary golden files directory"""
    golden_path = tmp_path / "golden"
    golden_path.mkdir()
    
    # Write golden files
    (golden_path / "mtga.txt").write_text(GOLDEN_MTGA)
    (golden_path / "moxfield.txt").write_text(GOLDEN_MOXFIELD)
    (golden_path / "archidekt.txt").write_text(GOLDEN_ARCHIDEKT)
    (golden_path / "tappedout.txt").write_text(GOLDEN_TAPPEDOUT)
    
    return golden_path

def test_snapshot_update(golden_dir):
    """Test snapshot update mechanism"""
    # This would be used in CI to update golden files when needed
    # Run with: pytest tests/test_export_golden.py --snapshot-update
    pass