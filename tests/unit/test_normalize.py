"""Test card name normalization."""
import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

def norm_name(raw: str) -> str:
    """Normalize card name for comparison."""
    import unicodedata
    # Remove accents
    nfkd = unicodedata.normalize('NFKD', raw)
    normalized = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    # Lowercase and strip
    return normalized.lower().strip()

@pytest.mark.parametrize("raw,exp", [
    ("Fable of the Mirror-Breaker // Reflection of Kiki-Jiki", "fable of the mirror-breaker // reflection of kiki-jiki"),
    ("Brazen Borrower // Petty Theft", "brazen borrower // petty theft"),
    ("Thoughtseize", "thoughtseize"),
    ("Île", "ile"),  # diacritics folding
    ("Forêt", "foret"),  # French Forest
    ("Fire // Ice", "fire // ice"),  # Split card
])
def test_norm_name(raw, exp):
    assert norm_name(raw) == exp