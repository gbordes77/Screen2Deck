from ..models import NormalizedDeck
def export_tappedout(deck: NormalizedDeck) -> str:
    return "\n".join([f"{c.qty} {c.name}" for c in deck.main]) + "\n\nSideboard\n" + "\n".join([f"{c.qty} {c.name}" for c in deck.side])