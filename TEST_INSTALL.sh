#!/bin/bash
# Test rapide de l'installation Screen2Deck

echo "🔍 Vérification de l'installation Screen2Deck"
echo "============================================="

# 1) Vérifier Docker
echo -n "Docker : "
if command -v docker &> /dev/null; then
    docker --version
else
    echo "❌ Non installé"
    exit 1
fi

# 2) Vérifier Docker Compose
echo -n "Docker Compose : "
if docker compose version &> /dev/null; then
    docker compose version
else
    echo "❌ Non installé"
    exit 1
fi

# 3) Vérifier la structure du projet
echo ""
echo "📁 Structure du projet :"
for dir in backend webapp validation_set; do
    if [ -d "$dir" ]; then
        echo "   ✅ $dir/"
    else
        echo "   ❌ $dir/ manquant"
    fi
done

# 4) Vérifier les fichiers critiques
echo ""
echo "📄 Fichiers critiques :"
files=(
    "docker-compose.yml"
    "backend/requirements.txt"
    "backend/app/main.py"
    "webapp/package.json"
)
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ $file"
    else
        echo "   ❌ $file manquant"
    fi
done

# 5) Vérifier les images de test
echo ""
echo "🖼️  Images de validation :"
count=$(ls -1 decklist-validation-set/*.{jpg,jpeg,png,webp} 2>/dev/null | wc -l)
echo "   📸 $count images disponibles dans decklist-validation-set/"

echo ""
echo "✨ Pour démarrer le projet : ./START.sh"
echo "📚 Documentation : MTG_Deck_Scanner_Docs_v2/"