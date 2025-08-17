#!/usr/bin/env python3
"""Benchmark simplifié pour tester les métriques OCR"""

import sys
import os
import time
import glob
sys.path.insert(0, 'backend')

def benchmark_ocr():
    """Benchmark OCR sur les images de validation"""
    print("🎯 Benchmark OCR Screen2Deck\n")
    
    # Import EasyOCR
    try:
        import easyocr
        reader = easyocr.Reader(['en'], gpu=False)
        print("✅ EasyOCR initialisé (CPU)\n")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return
    
    # Trouver les images
    images = glob.glob("validation_set/*.jpeg") + glob.glob("validation_set/*.jpg")
    print(f"📸 {len(images)} images trouvées\n")
    
    # Métriques
    results = []
    total_time = 0
    
    # Traiter chaque image
    for i, img_path in enumerate(images[:5], 1):  # Limité à 5 pour le test
        img_name = os.path.basename(img_path)
        print(f"[{i}/{min(5, len(images))}] {img_name}")
        
        start = time.time()
        try:
            result = reader.readtext(img_path)
            elapsed = time.time() - start
            total_time += elapsed
            
            # Calculer confiance
            if result:
                mean_conf = sum(r[2] for r in result) / len(result)
            else:
                mean_conf = 0
            
            # Extraire cartes (lignes avec nombres)
            cards = []
            for bbox, text, conf in result:
                # Détection simple: commence par un chiffre
                text = text.strip()
                if text and text[0].isdigit() and conf > 0.5:
                    cards.append(text)
            
            results.append({
                'image': img_name,
                'time': elapsed,
                'zones': len(result),
                'cards': len(cards),
                'confidence': mean_conf
            })
            
            print(f"  ⏱️ {elapsed:.2f}s | 📝 {len(result)} zones | 🎴 {len(cards)} cartes | 📊 {mean_conf:.0%} conf")
            
        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            results.append({
                'image': img_name,
                'time': 0,
                'zones': 0,
                'cards': 0,
                'confidence': 0
            })
    
    # Statistiques
    print("\n" + "="*60)
    print("📊 RÉSULTATS DU BENCHMARK")
    print("="*60)
    
    if results:
        times = [r['time'] for r in results if r['time'] > 0]
        confs = [r['confidence'] for r in results if r['confidence'] > 0]
        cards = [r['cards'] for r in results]
        
        if times:
            print(f"⏱️ Temps moyen: {sum(times)/len(times):.2f}s")
            print(f"⏱️ Temps P95: {sorted(times)[int(len(times)*0.95)]:.2f}s")
            print(f"⏱️ Temps max: {max(times):.2f}s")
        
        if confs:
            print(f"📊 Confiance moyenne: {sum(confs)/len(confs):.1%}")
            print(f"📊 Images > 62%: {sum(1 for c in confs if c >= 0.62)}/{len(confs)}")
        
        print(f"🎴 Cartes moyennes/image: {sum(cards)/len(cards):.1f}")
        
        # Validation des métriques annoncées
        print("\n🎯 VALIDATION DES MÉTRIQUES ANNONCÉES:")
        
        # P95 < 5s ?
        if times and sorted(times)[int(len(times)*0.95)] < 5:
            print("✅ P95 < 5s (cible atteinte)")
        else:
            print("❌ P95 >= 5s (cible manquée)")
        
        # Accuracy (basée sur détection de cartes)
        accuracy = sum(1 for r in results if r['cards'] >= 10) / len(results) * 100
        print(f"📈 Précision estimée: {accuracy:.1f}% (cartes détectées >= 10)")
        
        if accuracy >= 95:
            print("✅ Accuracy >= 95% (cible atteinte)")
        else:
            print("⚠️ Accuracy < 95% (mais test limité)")

if __name__ == "__main__":
    benchmark_ocr()