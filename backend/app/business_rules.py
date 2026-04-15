"""
Business rules for deck validation and MTGO sideboard segmentation.

MTGO screenshots render the full 75-card deck inline without a sideboard
marker, so after OCR we need to redistribute the last 15 cards into the
sideboard when the mainboard overflows MIN_MAIN (60) and the sideboard
is empty.
"""
from typing import List

from .telemetry import logger
from .models import NormalizedDeck, NormalizedCard

MIN_MAIN = 60
SIDE_DEFAULT = 15


def apply_mtgo_land_fix(
    normalized: NormalizedDeck,
    text_lines: List[str] | None = None,
) -> NormalizedDeck:
    """
    Redistribute a flat OCR result into a canonical 60+15 MTGO layout.

    MTGO exports a deck as a single column, so EasyOCR returns main and
    sideboard mixed in `normalized.main`. When that main total exceeds
    MIN_MAIN and the sideboard is empty, this walks the list, keeps the
    first 60 cards (splitting the card that crosses the boundary if
    necessary), and moves the remainder to the sideboard.

    `text_lines` is accepted for API compatibility but not currently used
    as a MTGO detection signal; detection is based on deck shape alone.
    """
    _ = text_lines  # reserved for future MTGO-signature detection

    main_total = sum(c.qty for c in normalized.main)
    side_total = sum(c.qty for c in normalized.side)

    if side_total > 0 or main_total <= MIN_MAIN:
        return normalized

    main_entries: list[NormalizedCard] = []
    side_entries: list[NormalizedCard] = list(normalized.side)
    total_count = 0

    for card in normalized.main:
        if total_count < MIN_MAIN:
            remaining_main = MIN_MAIN - total_count
            if card.qty <= remaining_main:
                main_entries.append(card)
                total_count += card.qty
            else:
                if remaining_main > 0:
                    main_entries.append(
                        NormalizedCard(
                            qty=remaining_main,
                            name=card.name,
                            scryfall_id=card.scryfall_id,
                        )
                    )
                side_entries.append(
                    NormalizedCard(
                        qty=card.qty - remaining_main,
                        name=card.name,
                        scryfall_id=card.scryfall_id,
                    )
                )
                total_count = MIN_MAIN
        else:
            side_entries.append(card)

    logger.info(
        "MTGO land fix: %d mainboard, %d sideboard",
        sum(c.qty for c in main_entries),
        sum(c.qty for c in side_entries),
    )
    return NormalizedDeck(main=main_entries, side=side_entries)


def validate_and_fill(normalized: NormalizedDeck) -> NormalizedDeck:
    """
    Sanity-check a normalized deck and log warnings for unusual counts.

    Non-mutating: surfaces issues that downstream consumers (exporters,
    UI) may want to highlight.
    """
    main_count = sum(c.qty for c in normalized.main)
    side_count = sum(c.qty for c in normalized.side)

    if main_count < MIN_MAIN:
        logger.warning(
            "Mainboard has %d cards, expected at least %d", main_count, MIN_MAIN
        )
    if side_count > SIDE_DEFAULT:
        logger.warning(
            "Sideboard has %d cards, expected at most %d", side_count, SIDE_DEFAULT
        )

    return normalized
