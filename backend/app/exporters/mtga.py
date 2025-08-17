from ..models import NormalizedDeck
def export_mtga(deck: NormalizedDeck) -> str:
    lines = ["Deck"]
    for c in deck.main: lines.append(f"{c.qty} {c.name}")
    lines.append(""); lines.append("Sideboard")
    for c in deck.side: lines.append(f"{c.qty} {c.name}")
    return "\n".join(lines)