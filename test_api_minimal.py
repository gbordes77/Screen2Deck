#!/usr/bin/env python3
"""Test minimal de l'API sans dépendances complexes"""

import sys
import os
sys.path.insert(0, 'backend')
os.chdir('backend')

# Désactiver telemetry
os.environ['FEATURE_TELEMETRY'] = 'false'
os.environ['OTEL_SDK_DISABLED'] = 'true'

def test_imports():
    """Test des imports essentiels"""
    errors = []
    
    print("🔍 Test des imports...")
    
    try:
        from fastapi import FastAPI
        print("✅ FastAPI importé")
    except ImportError as e:
        errors.append(f"❌ FastAPI: {e}")
    
    try:
        import easyocr
        print("✅ EasyOCR importé")
    except ImportError as e:
        errors.append(f"❌ EasyOCR: {e}")
    
    try:
        from app.config import S
        print(f"✅ Config importée (OCR_MIN_CONF={S.OCR_MIN_CONF})")
    except Exception as e:
        errors.append(f"❌ Config: {e}")
    
    try:
        from app.pipeline.ocr import run_easyocr_best_of
        print("✅ Pipeline OCR importé")
    except Exception as e:
        errors.append(f"❌ Pipeline OCR: {e}")
    
    try:
        from app.matching.scryfall_client import SCRYFALL
        print("✅ Scryfall client importé")
    except Exception as e:
        errors.append(f"❌ Scryfall: {e}")
    
    return errors

def create_minimal_app():
    """Créer une app FastAPI minimale"""
    from fastapi import FastAPI
    
    app = FastAPI(title="Screen2Deck Minimal")
    
    @app.get("/health")
    def health():
        return {"status": "healthy", "service": "screen2deck-minimal"}
    
    @app.get("/test-ocr")
    def test_ocr():
        import easyocr
        reader = easyocr.Reader(['en'], gpu=False)
        return {"ocr": "ready", "gpu": False}
    
    return app

if __name__ == "__main__":
    errors = test_imports()
    
    if errors:
        print("\n❌ Erreurs détectées:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    
    print("\n✅ Tous les imports OK!")
    print("\n🚀 Création app minimale...")
    
    app = create_minimal_app()
    
    print("📡 Démarrage serveur sur http://localhost:8080")
    print("   Test avec: curl http://localhost:8080/health")
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)