"""Real tests for backend.app.business_rules.

These replace the earlier local-stub tests that defined their own
``fix_mtgo_lands_count_bug`` function and never touched the backend
package. The assertions below exercise the code path that main.py
actually calls in production.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.business_rules import (  # noqa: E402
    MIN_MAIN,
    SIDE_DEFAULT,
    apply_mtgo_land_fix,
    validate_and_fill,
)
from app.models import NormalizedCard, NormalizedDeck  # noqa: E402


def _card(qty: int, name: str) -> NormalizedCard:
    return NormalizedCard(qty=qty, name=name, scryfall_id=None)


def test_mtgo_redistribution_single_card_over_60():
    """A flat MTGO OCR result with 64 copies of one card should split
    into 60 mainboard + 4 sideboard."""
    deck = NormalizedDeck(main=[_card(64, "Island")], side=[])
    result = apply_mtgo_land_fix(deck)
    assert sum(c.qty for c in result.main) == MIN_MAIN
    assert sum(c.qty for c in result.side) == 4
    assert result.main[0].name == "Island"
    assert result.side[0].name == "Island"


def test_mtgo_redistribution_multiple_cards_over_60():
    """Main count of 75 with several distinct cards splits at the
    boundary — the card crossing 60 is split between the two sections."""
    deck = NormalizedDeck(
        main=[
            _card(20, "Island"),
            _card(20, "Opt"),
            _card(20, "Counterspell"),
            _card(15, "Negate"),
        ],
        side=[],
    )
    result = apply_mtgo_land_fix(deck)
    main_total = sum(c.qty for c in result.main)
    side_total = sum(c.qty for c in result.side)
    assert main_total == MIN_MAIN
    assert side_total == 15
    assert side_total <= SIDE_DEFAULT


def test_mtgo_noop_when_side_present():
    """If the sideboard is already populated the parser has clearly
    segmented the deck itself — we must not touch it."""
    deck = NormalizedDeck(
        main=[_card(64, "Island")],
        side=[_card(1, "Duress")],
    )
    result = apply_mtgo_land_fix(deck)
    assert sum(c.qty for c in result.main) == 64
    assert sum(c.qty for c in result.side) == 1


def test_mtgo_noop_when_main_under_60():
    """Decks that didn't overflow the mainboard threshold are left
    alone (Limited, EDH, partial captures)."""
    deck = NormalizedDeck(main=[_card(40, "Island")], side=[])
    result = apply_mtgo_land_fix(deck)
    assert sum(c.qty for c in result.main) == 40
    assert len(result.side) == 0


def test_validate_and_fill_is_non_mutating():
    """validate_and_fill only logs warnings; it must return the deck
    unchanged even when counts are unusual."""
    deck = NormalizedDeck(
        main=[_card(55, "Island")],
        side=[_card(20, "Negate")],
    )
    result = validate_and_fill(deck)
    assert result is deck
