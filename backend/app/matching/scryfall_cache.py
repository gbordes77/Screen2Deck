"""
Scryfall offline-first cache with SQLite
Provides fast local lookups with online fallback
"""

import sqlite3
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from pathlib import Path
import aiohttp
import asyncio
from contextlib import contextmanager

from ..telemetry import logger

class ScryfallCache:
    """SQLite-based Scryfall cache with TTL and ETag support"""
    
    def __init__(self, db_path: str = "./data/scryfall_cache.db", ttl_days: int = 7):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(days=ttl_days)
        self.session = None
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database with schema"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    id TEXT PRIMARY KEY,
                    name_norm TEXT NOT NULL,
                    name_printed TEXT NOT NULL,
                    lang TEXT DEFAULT 'en',
                    layout TEXT,
                    faces TEXT,  -- JSON array of face objects
                    oracle_id TEXT,
                    scryfall_id TEXT UNIQUE,
                    cmc REAL,
                    type_line TEXT,
                    oracle_text TEXT,
                    mana_cost TEXT,
                    colors TEXT,  -- JSON array
                    color_identity TEXT,  -- JSON array
                    legalities TEXT,  -- JSON object
                    set_code TEXT,
                    collector_number TEXT,
                    rarity TEXT,
                    image_uris TEXT,  -- JSON object
                    prices TEXT,  -- JSON object
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    etag TEXT,
                    cache_hit_count INTEGER DEFAULT 0
                )
            """)
            
            # Create indexes for fast lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_name_norm ON cards(name_norm)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_oracle_id ON cards(oracle_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scryfall_id ON cards(scryfall_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_updated_at ON cards(updated_at)")
            
            # Metadata table for bulk data tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup"""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def normalize_name(self, name: str) -> str:
        """Normalize card name for matching"""
        import unicodedata
        # Remove diacritics
        normalized = unicodedata.normalize('NFD', name)
        normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        # Lowercase and strip
        normalized = normalized.lower().strip()
        # Remove punctuation for matching
        normalized = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in normalized)
        # Collapse spaces
        normalized = ' '.join(normalized.split())
        return normalized
    
    def get_card_by_name(self, name: str, fuzzy: bool = False) -> Optional[Dict]:
        """Get card from cache by name"""
        norm_name = self.normalize_name(name)
        
        with self._get_connection() as conn:
            # Try exact match first
            cursor = conn.execute(
                "SELECT * FROM cards WHERE name_norm = ? ORDER BY updated_at DESC LIMIT 1",
                (norm_name,)
            )
            row = cursor.fetchone()
            
            if not row and fuzzy:
                # Try fuzzy match with LIKE
                cursor = conn.execute(
                    "SELECT * FROM cards WHERE name_norm LIKE ? ORDER BY updated_at DESC LIMIT 10",
                    (f"%{norm_name}%",)
                )
                rows = cursor.fetchall()
                
                if rows:
                    # Use fuzzy matching to find best match
                    from rapidfuzz import fuzz
                    best_score = 0
                    best_row = None
                    
                    for r in rows:
                        score = fuzz.ratio(norm_name, r['name_norm'])
                        if score > best_score:
                            best_score = score
                            best_row = r
                    
                    if best_score >= 85:  # Threshold for fuzzy match
                        row = best_row
            
            if row:
                # Check TTL
                updated = datetime.fromisoformat(row['updated_at'])
                if datetime.utcnow() - updated < self.ttl:
                    # Update hit counter
                    conn.execute(
                        "UPDATE cards SET cache_hit_count = cache_hit_count + 1 WHERE id = ?",
                        (row['id'],)
                    )
                    conn.commit()
                    
                    # Convert row to dict
                    card = dict(row)
                    # Parse JSON fields
                    for field in ['faces', 'colors', 'color_identity', 'legalities', 'image_uris', 'prices']:
                        if card.get(field):
                            try:
                                card[field] = json.loads(card[field])
                            except:
                                card[field] = None
                    
                    logger.info(f"Cache hit for card: {name}")
                    return card
                else:
                    logger.info(f"Cache expired for card: {name}")
            
            logger.info(f"Cache miss for card: {name}")
            return None
    
    def save_card(self, card_data: Dict):
        """Save card to cache"""
        # Normalize the name
        norm_name = self.normalize_name(card_data.get('name', ''))
        
        # Generate ID (hash of oracle_id or name)
        card_id = card_data.get('oracle_id') or hashlib.md5(norm_name.encode()).hexdigest()
        
        # Prepare JSON fields
        json_fields = {}
        for field in ['faces', 'colors', 'color_identity', 'legalities', 'image_uris', 'prices']:
            if field in card_data:
                json_fields[field] = json.dumps(card_data[field])
            else:
                json_fields[field] = None
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cards (
                    id, name_norm, name_printed, lang, layout, faces,
                    oracle_id, scryfall_id, cmc, type_line, oracle_text,
                    mana_cost, colors, color_identity, legalities,
                    set_code, collector_number, rarity, image_uris, prices,
                    updated_at, etag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (
                card_id,
                norm_name,
                card_data.get('name', ''),
                card_data.get('lang', 'en'),
                card_data.get('layout'),
                json_fields['faces'],
                card_data.get('oracle_id'),
                card_data.get('id'),  # scryfall_id
                card_data.get('cmc'),
                card_data.get('type_line'),
                card_data.get('oracle_text'),
                card_data.get('mana_cost'),
                json_fields['colors'],
                json_fields['color_identity'],
                json_fields['legalities'],
                card_data.get('set'),
                card_data.get('collector_number'),
                card_data.get('rarity'),
                json_fields['image_uris'],
                json_fields['prices'],
                card_data.get('etag')
            ))
            conn.commit()
            logger.info(f"Cached card: {card_data.get('name')}")
    
    async def fetch_card_online(self, name: str) -> Optional[Dict]:
        """Fetch card from Scryfall API"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            # Use fuzzy search endpoint
            url = "https://api.scryfall.com/cards/named"
            params = {"fuzzy": name}
            
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    card_data = await resp.json()
                    # Add ETag for cache validation
                    card_data['etag'] = resp.headers.get('ETag')
                    # Save to cache
                    self.save_card(card_data)
                    return card_data
                elif resp.status == 404:
                    logger.warning(f"Card not found on Scryfall: {name}")
                    return None
                else:
                    logger.error(f"Scryfall API error {resp.status} for: {name}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching card from Scryfall: {e}")
            return None
    
    async def resolve_card(self, name: str) -> Optional[Dict]:
        """Resolve card with offline-first strategy"""
        # 1. Try exact match from cache
        card = self.get_card_by_name(name, fuzzy=False)
        if card:
            return card
        
        # 2. Try fuzzy match from cache
        card = self.get_card_by_name(name, fuzzy=True)
        if card:
            return card
        
        # 3. Fetch from Scryfall API
        card = await self.fetch_card_online(name)
        if card:
            return card
        
        logger.warning(f"Could not resolve card: {name}")
        return None
    
    def handle_special_layouts(self, card: Dict) -> Dict:
        """Handle DFC, Split, Adventure cards"""
        layout = card.get('layout', 'normal')
        
        if layout in ['transform', 'modal_dfc']:
            # Double-faced cards
            faces = card.get('card_faces', [])
            if faces:
                # Use front face name for display
                card['display_name'] = faces[0].get('name', card.get('name'))
                # Store both faces for export
                card['faces'] = faces
        
        elif layout == 'split':
            # Split cards (Fire // Ice)
            faces = card.get('card_faces', [])
            if len(faces) == 2:
                card['display_name'] = f"{faces[0]['name']} // {faces[1]['name']}"
        
        elif layout == 'adventure':
            # Adventure cards
            faces = card.get('card_faces', [])
            if faces:
                # Use creature name as primary
                card['display_name'] = faces[0].get('name', card.get('name'))
        
        return card
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as total FROM cards")
            total = cursor.fetchone()['total']
            
            cursor = conn.execute("""
                SELECT COUNT(*) as expired 
                FROM cards 
                WHERE datetime(updated_at, '+7 days') < datetime('now')
            """)
            expired = cursor.fetchone()['expired']
            
            cursor = conn.execute("SELECT SUM(cache_hit_count) as hits FROM cards")
            hits = cursor.fetchone()['hits'] or 0
            
            return {
                'total_cards': total,
                'expired_cards': expired,
                'active_cards': total - expired,
                'total_hits': hits,
                'db_size_mb': self.db_path.stat().st_size / 1024 / 1024 if self.db_path.exists() else 0
            }
    
    def cleanup_expired(self):
        """Remove expired entries"""
        with self._get_connection() as conn:
            conn.execute("""
                DELETE FROM cards 
                WHERE datetime(updated_at, '+7 days') < datetime('now')
            """)
            conn.commit()
            logger.info("Cleaned up expired cache entries")
    
    async def close(self):
        """Close session"""
        if self.session:
            await self.session.close()

# Global cache instance
scryfall_cache = ScryfallCache()