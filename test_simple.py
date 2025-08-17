#!/usr/bin/env python3
"""Test simple pour vérifier les composants essentiels"""

import sys
import os

def test_imports():
    """Test des imports essentiels"""
    errors = []
    
    # Test imports OCR
    try:
        import easyocr
        print("✅ EasyOCR importé")
    except ImportError as e:
        errors.append(f"❌ EasyOCR: {e}")
    
    # Test imports web
    try:
        import fastapi
        import uvicorn
        print("✅ FastAPI/Uvicorn importés")
    except ImportError as e:
        errors.append(f"❌ FastAPI: {e}")
    
    # Test Redis
    try:
        import redis
        client = redis.Redis(host='localhost', port=6379, db=0)
        client.ping()
        print("✅ Redis connecté")
    except Exception as e:
        errors.append(f"❌ Redis: {e}")
    
    # Test fichiers OCR
    if os.path.exists("backend/app/pipeline/ocr.py"):
        print("✅ Module OCR trouvé")
    else:
        errors.append("❌ Module OCR manquant")
    
    # Test fichiers Scryfall
    if os.path.exists("backend/app/matching/scryfall_client.py"):
        print("✅ Module Scryfall trouvé")
    else:
        errors.append("❌ Module Scryfall manquant")
    
    # Test config
    if os.path.exists("backend/app/config.py"):
        print("✅ Config trouvé")
        # Check seuil
        try:
            with open("backend/app/config.py") as f:
                if "0.62" in f.read():
                    print("✅ Seuil 62% configuré")
        except:
            pass
    
    return errors

if __name__ == "__main__":
    errors = test_imports()
    
    print("\n📊 Résumé:")
    if errors:
        print("Erreurs détectées:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("✅ Tous les tests passent !")
        sys.exit(0)