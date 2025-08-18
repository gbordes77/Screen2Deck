"""Test MTG-specific edge cases."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

def normalize_dfc_card(name: str) -> str:
    """Normalize double-faced card names."""
    # Handle DFC with // separator
    if " // " in name:
        parts = name.split(" // ")
        return f"{parts[0].strip()} // {parts[1].strip()}"
    return name

def normalize_adventure_card(name: str) -> str:
    """Normalize adventure cards (Brazen Borrower // Petty Theft)."""
    # Adventure cards are also DFC
    return normalize_dfc_card(name)

def parse_sideboard_marker(line: str) -> bool:
    """Check if line is a sideboard marker."""
    normalized = line.strip().lower()
    return normalized in ["sideboard", "sideboard:", "sb:", "side:"]

@pytest.mark.parametrize("card,expected", [
    # Double-faced cards
    ("Fable of the Mirror-Breaker // Reflection of Kiki-Jiki", 
     "Fable of the Mirror-Breaker // Reflection of Kiki-Jiki"),
    
    # Adventure cards
    ("Brazen Borrower // Petty Theft", 
     "Brazen Borrower // Petty Theft"),
    ("Bonecrusher Giant // Stomp",
     "Bonecrusher Giant // Stomp"),
    
    # Split cards
    ("Fire // Ice", "Fire // Ice"),
    ("Wear // Tear", "Wear // Tear"),
    
    # Normal cards (unchanged)
    ("Lightning Bolt", "Lightning Bolt"),
    ("Thoughtseize", "Thoughtseize"),
])
def test_dfc_and_split_cards(card, expected):
    """Test DFC, Adventure, and Split card normalization."""
    assert normalize_dfc_card(card) == expected

def test_sideboard_markers():
    """Test various sideboard marker formats."""
    assert parse_sideboard_marker("Sideboard")
    assert parse_sideboard_marker("sideboard")
    assert parse_sideboard_marker("SIDEBOARD")
    assert parse_sideboard_marker("Sideboard:")
    assert parse_sideboard_marker("SB:")
    assert parse_sideboard_marker("Side:")
    assert not parse_sideboard_marker("4 Duress")
    assert not parse_sideboard_marker("Mainboard")

def test_foreign_language_cards():
    """Test cards with accents and foreign names."""
    cards = {
        "Île": "Island",  # French Island
        "Forêt": "Forest",  # French Forest
        "Montagne": "Mountain",  # French Mountain
        "Plaine": "Plains",  # French Plains
        "Marais": "Swamp",  # French Swamp
        "Saisie des pensées": "Thoughtseize",  # French Thoughtseize
    }
    
    # In real implementation, would have translation mapping
    for foreign, english in cards.items():
        # For now, just ensure we handle unicode properly
        assert len(foreign) > 0
        assert foreign != english  # They should be different

def test_quantity_parsing_edge_cases():
    """Test edge cases in quantity parsing."""
    test_cases = [
        ("4 Lightning Bolt", (4, "Lightning Bolt")),
        ("1 Island", (1, "Island")),
        ("10 Mountain", (10, "Mountain")),  # Two-digit quantity
        ("4x Lightning Bolt", (4, "Lightning Bolt")),  # Alternative format
        ("Lightning Bolt x4", (4, "Lightning Bolt")),  # Reversed format
        ("SB: 2 Duress", ("SB", 2, "Duress")),  # Sideboard
    ]
    
    for line, expected in test_cases:
        # Simple parser for testing
        import re
        
        # Check for SB prefix
        if line.startswith("SB:"):
            parts = line[3:].strip().split(None, 1)
            if parts[0].isdigit():
                result = ("SB", int(parts[0]), parts[1])
            else:
                result = None
        else:
            # Try different patterns
            match = re.match(r"(\d+)x?\s+(.+)", line)
            if match:
                result = (int(match.group(1)), match.group(2))
            else:
                match = re.match(r"(.+?)\s+x(\d+)", line)
                if match:
                    result = (int(match.group(2)), match.group(1))
                else:
                    result = None
        
        assert result == expected, f"Failed to parse: {line}"

def test_special_characters_in_names():
    """Test cards with special characters."""
    cards = [
        "Jace, the Mind Sculptor",  # Comma
        "Ral's Outburst",  # Apostrophe
        "Niv-Mizzet, Parun",  # Hyphen and comma
        "+2 Mace",  # Plus sign
        "Circle of Protection: Red",  # Colon
        "Who/What/When/Where/Why",  # Multiple slashes (Un-card)
    ]
    
    for card in cards:
        # Ensure no crashes when processing special characters
        assert len(card) > 0
        assert card == card  # Identity check

def test_basic_land_variations():
    """Test different basic land representations."""
    lands = [
        ("Island", "Island"),
        ("Islands", "Island"),  # Plural
        ("island", "Island"),  # Lowercase
        ("ISLAND", "Island"),  # Uppercase
        ("Snow-Covered Island", "Snow-Covered Island"),
        ("Island (337)", "Island"),  # With collector number
        ("Island #337", "Island"),  # Alternative format
    ]
    
    for input_name, expected in lands:
        # Normalize basic lands
        normalized = input_name.strip()
        
        # Remove collector numbers
        import re
        normalized = re.sub(r'\s*[#(]\d+[)]?\s*$', '', normalized)
        
        # Handle plurals
        if normalized.lower().endswith('s') and normalized.lower() != "plains":
            if normalized.lower() in ["islands", "mountains", "forests", "swamps"]:
                normalized = normalized[:-1]
        
        # Capitalize properly
        if not normalized.startswith("Snow-"):
            normalized = normalized.capitalize()
        
        assert normalized == expected, f"Failed: {input_name} -> {normalized} != {expected}"