#!/usr/bin/env python3
"""
Build offline Scryfall seed database from validation_set/truth/*.txt
No network calls - 100% local generation for air-gapped demos
"""
import sqlite3
import pathlib
import re
import json
import unicodedata
import sys

TRUTH_DIR = pathlib.Path("validation_set/truth")
DB_PATH = pathlib.Path("data/scryfall.sqlite")

def norm(s: str) -> str:
    """Normalize card name for fuzzy matching"""
    # Remove accents
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    # Lowercase and keep only alphanumeric
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def parse_truth(filepath: pathlib.Path):
    """Parse truth file to extract card names"""
    cards = []
    
    # Skip if file doesn't exist
    if not filepath.exists():
        return cards
        
    for line in filepath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue
            
        # Check for Sideboard section
        if line.lower() == "sideboard":
            continue
            
        # Parse quantity and name
        match = re.match(r"^(\d+)\s+(.+)$", line)
        if not match:
            continue
            
        qty = int(match.group(1))
        name = match.group(2).strip()
        
        # Remove sideboard markers if present
        name = re.sub(r"^SB:\s*", "", name, flags=re.I)
        
        # Remove set codes in parentheses
        name = re.sub(r"\s*\([^)]+\)\s*$", "", name)
        
        cards.append((qty, name))
    
    return cards

def main():
    """Build the offline seed database"""
    # Create data directory if needed
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if truth directory exists
    if not TRUTH_DIR.exists():
        print(f"Warning: {TRUTH_DIR} not found, creating empty database")
        TRUTH_DIR.mkdir(parents=True, exist_ok=True)
    
    # Collect all unique card names
    all_names = set()
    
    # Add some essential lands for testing
    basic_lands = ["Island", "Plains", "Swamp", "Mountain", "Forest"]
    all_names.update(basic_lands)
    
    # Parse all truth files
    truth_files = list(TRUTH_DIR.glob("*.txt"))
    if truth_files:
        print(f"Found {len(truth_files)} truth files")
        for filepath in sorted(truth_files):
            print(f"  Processing {filepath.name}")
            for qty, name in parse_truth(filepath):
                all_names.add(name)
    else:
        print("No truth files found, using basic lands only")
    
    # Add some common MTG cards for demo purposes
    demo_cards = [
        "Lightning Bolt",
        "Counterspell",
        "Path to Exile",
        "Thoughtseize",
        "Brainstorm",
        "Fatal Push",
        "Swords to Plowshares",
        "Birds of Paradise",
        "Llanowar Elves",
        "Sol Ring",
        "Mana Crypt",
        "Black Lotus",
        "Ancestral Recall",
        "Time Walk",
        "Mox Sapphire",
        # DFC cards
        "Fable of the Mirror-Breaker // Reflection of Kiki-Jiki",
        "Delver of Secrets // Insectile Aberration",
        # Split cards
        "Fire // Ice",
        "Wear // Tear",
        # Adventure cards
        "Brazen Borrower // Petty Theft",
        "Bonecrusher Giant // Stomp",
    ]
    all_names.update(demo_cards)
    
    # Create SQLite database
    print(f"\nCreating database at {DB_PATH}")
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    # Enable WAL mode for better concurrency
    cur.execute("PRAGMA journal_mode=WAL;")
    
    # Create cards table matching Scryfall schema
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cards(
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            name TEXT NOT NULL UNIQUE,
            name_norm TEXT NOT NULL,
            faces TEXT NOT NULL DEFAULT '[]',
            lang TEXT NOT NULL DEFAULT 'en',
            collector_number TEXT DEFAULT '',
            set_code TEXT DEFAULT 'demo',
            rarity TEXT DEFAULT 'common',
            colors TEXT DEFAULT '[]',
            mana_cost TEXT DEFAULT '',
            cmc REAL DEFAULT 0,
            type_line TEXT DEFAULT '',
            oracle_text TEXT DEFAULT '',
            power TEXT DEFAULT '',
            toughness TEXT DEFAULT '',
            keywords TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Create indexes for faster lookups
    cur.execute("CREATE INDEX IF NOT EXISTS idx_name_norm ON cards(name_norm);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_name ON cards(name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_set_code ON cards(set_code);")
    
    # Prepare rows for insertion
    rows = []
    for name in sorted(all_names):
        # Generate a pseudo-ID
        pseudo_id = f"demo_{hash(name) % 1000000:06d}"
        
        # Handle double-faced and split cards
        faces = []
        if " // " in name:
            faces = name.split(" // ")
        
        row = (
            pseudo_id,
            name,
            norm(name),
            json.dumps(faces),
            "en",  # language
            "",    # collector_number
            "demo",  # set_code
            "common",  # rarity
            "[]",  # colors
            "",    # mana_cost
            0,     # cmc
            "",    # type_line
            "",    # oracle_text
            "",    # power
            "",    # toughness
            "[]"   # keywords
        )
        rows.append(row)
    
    # Insert cards
    cur.executemany("""
        INSERT OR REPLACE INTO cards(
            id, name, name_norm, faces, lang,
            collector_number, set_code, rarity, colors,
            mana_cost, cmc, type_line, oracle_text,
            power, toughness, keywords
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    
    # Create a metadata table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS metadata(
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    
    cur.execute("""
        INSERT OR REPLACE INTO metadata(key, value) VALUES
        ('version', '1.0.0'),
        ('created', datetime('now')),
        ('card_count', ?),
        ('mode', 'offline_demo')
    """, (len(rows),))
    
    # Commit and close
    con.commit()
    con.close()
    
    print(f"\n✅ Seeded {len(rows)} card names into {DB_PATH}")
    print(f"   - Basic lands: {len([n for n in all_names if n in basic_lands])}")
    print(f"   - From truth files: {len(all_names) - len(demo_cards) - len(basic_lands)}")
    print(f"   - Demo cards: {len([n for n in demo_cards if n in all_names])}")
    
    # Verify database
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    count = cur.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    con.close()
    
    print(f"\n📊 Database verification: {count} cards stored")
    print("🔒 Ready for offline demo - no network calls needed!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())