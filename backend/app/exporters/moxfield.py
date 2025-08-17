from ..models import NormalizedDeck
def export_moxfield(deck: NormalizedDeck) -> str:
    return "\n".join([f"{c.qty} {c.name}" for c in deck.main + deck.side])