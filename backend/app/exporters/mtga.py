from ..models import NormalizedDeck


def _mtga_name(name: str) -> str:
    """MTGA wants only the front face for DFC/MDFC/split/adventure cards."""
    return name.split(" // ")[0]


def export_mtga(deck: NormalizedDeck) -> str:
    lines = ["Deck"]
    for c in deck.main:
        lines.append(f"{c.qty} {_mtga_name(c.name)}")
    lines.append("")
    lines.append("Sideboard")
    for c in deck.side:
        lines.append(f"{c.qty} {_mtga_name(c.name)}")
    return "\n".join(lines)
