#!/usr/bin/env python3
"""Test direct de l'OCR sans serveur web"""

import sys
import os
import time
sys.path.insert(0, 'backend')

def test_ocr_direct():
    """Test OCR directement"""
    print("📊 Test OCR Direct\n")
    
    # Test EasyOCR import
    try:
        import easyocr
        print("✅ EasyOCR importé")
        reader = easyocr.Reader(['en'], gpu=False)
        print("✅ EasyOCR Reader créé (CPU mode)")
    except Exception as e:
        print(f"❌ EasyOCR: {e}")
        return False
    
    # Test image
    test_image = "validation_set/MTGA deck list_1535x728.jpeg"
    if not os.path.exists(test_image):
        print(f"❌ Image test manquante: {test_image}")
        return False
    print(f"✅ Image trouvée: {test_image}")
    
    # Test OCR
    print("\n🔍 Lancement OCR (peut prendre 10-30s)...")
    start = time.time()
    try:
        result = reader.readtext(test_image)
        elapsed = time.time() - start
        print(f"✅ OCR terminé en {elapsed:.2f}s")
        print(f"✅ {len(result)} zones de texte détectées")
        
        # Afficher quelques résultats
        print("\n📝 Premiers textes détectés:")
        for i, (bbox, text, conf) in enumerate(result[:5]):
            print(f"  - '{text}' (confiance: {conf:.2%})")
        
        # Calculer confiance moyenne
        if result:
            mean_conf = sum(r[2] for r in result) / len(result)
            print(f"\n📊 Confiance moyenne: {mean_conf:.2%}")
            if mean_conf >= 0.62:
                print("✅ Confiance >= 62% (seuil configuré)")
            else:
                print(f"⚠️ Confiance < 62% (seuil: 0.62)")
    except Exception as e:
        print(f"❌ Erreur OCR: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_ocr_direct()
    sys.exit(0 if success else 1)