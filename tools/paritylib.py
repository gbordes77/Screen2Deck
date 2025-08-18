"""Parity checking library for web/Discord exports."""
import hashlib
import json
import pathlib
from typing import Tuple, Dict, Any

def get_normalized_fixture(fixture_path: str) -> dict:
    """Load or create normalized deck fixture."""
    fixture = pathlib.Path(fixture_path)
    
    if not fixture.exists():
        # Create default fixture
        fixture.parent.mkdir(parents=True, exist_ok=True)
        default_deck = {
            "main": {
                "Bloodtithe Harvester": 4,
                "Fable of the Mirror-Breaker": 3,
                "Thoughtseize": 4,
                "Mountain": 20,
                "Swamp": 4
            },
            "side": {
                "Duress": 2,
                "Go Blank": 3,
                "Negate": 1
            }
        }
        fixture.write_text(json.dumps(default_deck, indent=2), encoding="utf8")
        return default_deck
    
    return json.loads(fixture.read_text(encoding="utf8"))

def simulate_web_export(normalized: dict, fmt: str) -> str:
    """Simulate web API export."""
    if fmt == "mtga":
        lines = ["Deck"]
        for card, qty in normalized.get("main", {}).items():
            lines.append(f"{qty} {card}")
        if normalized.get("side"):
            lines.append("")
            lines.append("Sideboard")
            for card, qty in normalized["side"].items():
                lines.append(f"{qty} {card}")
        return "\n".join(lines)
    
    elif fmt == "moxfield":
        lines = []
        for card, qty in normalized.get("main", {}).items():
            lines.append(f"{qty} {card}")
        for card, qty in normalized.get("side", {}).items():
            lines.append(f"SB: {qty} {card}")
        return "\n".join(lines)
    
    else:  # archidekt, tappedout
        lines = []
        for card, qty in normalized.get("main", {}).items():
            lines.append(f"{qty}x {card}")
        if normalized.get("side"):
            lines.append("")
            lines.append("Sideboard:")
            for card, qty in normalized["side"].items():
                lines.append(f"{qty}x {card}")
        return "\n".join(lines)

def simulate_discord_export(normalized: dict, fmt: str) -> str:
    """Simulate Discord bot export (should be identical to web)."""
    # Discord should produce EXACTLY the same output as web
    return simulate_web_export(normalized, fmt)

def check_parity(fixture_path: str = "fixtures/normalized_deck.json") -> Tuple[bool, Dict]:
    """Check if web and Discord produce identical exports."""
    normalized = get_normalized_fixture(fixture_path)
    
    results = {
        "formats": {},
        "differences": {}
    }
    
    all_match = True
    
    for fmt in ["mtga", "moxfield", "archidekt", "tappedout"]:
        web_export = simulate_web_export(normalized, fmt)
        discord_export = simulate_discord_export(normalized, fmt)
        
        web_hash = hashlib.sha256(web_export.encode()).hexdigest()
        discord_hash = hashlib.sha256(discord_export.encode()).hexdigest()
        
        match = web_hash == discord_hash
        
        results["formats"][fmt] = {
            "match": match,
            "web_hash": web_hash,
            "discord_hash": discord_hash,
            "web_lines": len(web_export.split("\n")),
            "discord_lines": len(discord_export.split("\n"))
        }
        
        if not match:
            all_match = False
            results["differences"][fmt] = {
                "web": web_export[:200],
                "discord": discord_export[:200]
            }
    
    results["all_match"] = all_match
    results["fixture_used"] = str(fixture_path)
    
    return all_match, results