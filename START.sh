#!/bin/bash
# Script de démarrage pour Screen2Deck (MTG Deck Scanner)
set -euo pipefail

echo "🎯 MTG Deck Scanner - Screen2Deck v2.0.2"
echo "========================================="
echo "Now with reproducible proof system!"
echo ""

# Configuration - NOUVEAU CHEMIN
PROJECT_DIR="/Volumes/DataDisk/_Projects/Screen2Deck"
cd "$PROJECT_DIR"

# 1) Arrêter les anciens conteneurs sur les ports 3000/8080
echo "🔪 Arrêt des conteneurs existants sur ports 3000/8080..."
docker ps --format '{{.ID}} {{.Ports}}' | grep -E '0\.0\.0\.0:(3000|8080)->' | awk '{print $1}' | xargs -r docker stop 2>/dev/null || true

# 2) Vérifier/créer les fichiers de configuration
echo "📝 Vérification de la configuration..."

# Créer .env si n'existe pas
if [ ! -f .env ]; then
    cat > .env <<'EOF'
APP_ENV=dev
PORT=8080
LOG_LEVEL=INFO

# OCR
ENABLE_VISION_FALLBACK=false
ENABLE_SUPERRES=false
OCR_MIN_CONF=0.62
OCR_MIN_LINES=10

# Scryfall (toujours vérifier les noms)
ALWAYS_VERIFY_SCRYFALL=true
ENABLE_SCRYFALL_ONLINE_FALLBACK=true
SCRYFALL_API_TIMEOUT=5
SCRYFALL_API_RATE_LIMIT_MS=120

# Cache & bulk
SCRYFALL_DB=./app/data/scryfall_cache.sqlite
SCRYFALL_BULK_PATH=./app/data/scryfall-default-cards.json
SCRYFALL_TIMEOUT=5

# Taille & fuzzy
MAX_IMAGE_MB=8
FUZZY_MATCH_TOPK=5

# Redis (optionnel)
USE_REDIS=false
REDIS_URL=redis://redis:6379/0
EOF
    echo "   ✅ Fichier .env créé"
fi

# Créer webapp/.env.local si n'existe pas
if [ ! -f webapp/.env.local ]; then
    cat > webapp/.env.local <<'EOF'
NEXT_PUBLIC_API_BASE=http://localhost:8080
EOF
    echo "   ✅ Fichier webapp/.env.local créé"
fi

# 3) Créer le dossier data si nécessaire
mkdir -p backend/app/data

# 4) Message pour Scryfall
if [ ! -f backend/app/data/scryfall-default-cards.json ]; then
    echo ""
    echo "⚠️  Premier démarrage détecté !"
    echo "   Le backend va télécharger la base Scryfall (~100MB)"
    echo "   Cela peut prendre quelques minutes..."
    echo ""
fi

# 5) Copier les images de validation si disponibles
if [ -d "decklist-validation-set" ] && [ ! "$(ls -A validation_set 2>/dev/null)" ]; then
    echo "📸 Copie des images de validation..."
    cp decklist-validation-set/*.{jpg,jpeg,webp,png} validation_set/ 2>/dev/null || true
    echo "   ✅ Images de test disponibles dans validation_set/"
fi

# 6) Lancer Docker Compose
echo ""
echo "🚀 Démarrage des services Docker..."
echo "   - Backend (FastAPI + EasyOCR) : http://localhost:8080"
echo "   - Frontend (Next.js) : http://localhost:3000"
echo "   - Redis : localhost:6379"
echo ""
echo "📌 Points clés du projet :"
echo "   • OCR : EasyOCR uniquement (jamais Tesseract) - CI enforced"
echo "   • Vérification Scryfall OBLIGATOIRE pour chaque carte"
echo "   • 4 formats d'export : MTGA, Moxfield, Archidekt, TappedOut"
echo "   • Metrics réalistes : 94% accuracy, 3.25s P95 latency"
echo ""
echo "🧪 Pour lancer les tests de preuve après démarrage :"
echo "   make test          # Tests unitaires + intégration"
echo "   make bench-day0    # Benchmarks avec métriques"
echo "   make golden        # Validation des exports"
echo "   make parity        # Parité Web/Discord"
echo ""

export COMPOSE_PROJECT_NAME=screen2deck
docker compose up --build

# Note: Le script reste actif pendant l'exécution
# Appuyer sur Ctrl+C pour arrêter