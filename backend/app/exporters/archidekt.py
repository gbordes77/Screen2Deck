import csv
import io

from ..models import NormalizedDeck


def export_archidekt(deck: NormalizedDeck) -> str:
    """Export a deck to Archidekt CSV, with proper escaping for card names
    that contain commas, quotes, or split markers (e.g. "Fire // Ice")."""
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(["Count", "Name", "Categories"])
    for c in deck.main:
        writer.writerow([c.qty, c.name, "Mainboard"])
    for c in deck.side:
        writer.writerow([c.qty, c.name, "Sideboard"])
    return buf.getvalue().rstrip("\n")
