from ..models import NormalizedDeck
def export_archidekt(deck: NormalizedDeck) -> str:
    rows = ["Count,Name,Categories"]
    for c in deck.main: rows.append(f"{c.qty},{c.name},Mainboard")
    for c in deck.side: rows.append(f"{c.qty},{c.name},Sideboard")
    return "\n".join(rows)