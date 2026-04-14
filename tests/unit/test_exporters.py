"""Real tests for backend.app.exporters.

These replace tests/e2e/test_exports_golden.py which was tautological
(it copied reference -> current and then asserted they were equal).
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.exporters.archidekt import export_archidekt  # noqa: E402
from app.exporters.mtga import export_mtga  # noqa: E402
from app.exporters.moxfield import export_moxfield  # noqa: E402
from app.exporters.tappedout import export_tappedout  # noqa: E402
from app.models import NormalizedCard, NormalizedDeck  # noqa: E402


def _deck(main, side=None):
    return NormalizedDeck(
        main=[NormalizedCard(qty=q, name=n, scryfall_id=None) for q, n in main],
        side=[NormalizedCard(qty=q, name=n, scryfall_id=None) for q, n in (side or [])],
    )


def test_archidekt_quotes_names_with_commas():
    """Cards whose names contain commas must be quoted by csv.writer
    so the output doesn't break downstream importers."""
    out = export_archidekt(_deck([(1, "Knight, Errant")]))
    assert '"Knight, Errant"' in out
    assert "Count,Name,Categories" in out


def test_archidekt_preserves_split_card_names():
    """Split cards use `//` which is not a CSV delimiter — they should
    pass through unquoted."""
    out = export_archidekt(_deck([(1, "Fire // Ice")]))
    assert "1,Fire // Ice,Mainboard" in out


def test_archidekt_sideboard_category():
    out = export_archidekt(_deck([(4, "Island")], [(2, "Negate")]))
    lines = out.splitlines()
    assert "4,Island,Mainboard" in lines
    assert "2,Negate,Sideboard" in lines


def test_mtga_export_structure():
    out = export_mtga(_deck([(4, "Lightning Bolt")], [(1, "Duress")]))
    assert "4 Lightning Bolt" in out
    assert "1 Duress" in out


def test_moxfield_export_structure():
    out = export_moxfield(_deck([(4, "Lightning Bolt")]))
    assert "4 Lightning Bolt" in out


def test_tappedout_export_structure():
    out = export_tappedout(_deck([(4, "Lightning Bolt")]))
    assert "Lightning Bolt" in out
