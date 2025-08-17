from .models import DeckSections, NormalizedDeck
MIN_MAIN = 60
SIDE_DEFAULT = 15
def apply_mtgo_land_fix(deck: DeckSections) -> DeckSections: return deck
def validate_and_fill(normalized: NormalizedDeck) -> NormalizedDeck: return normalized