# 🎯 Day 0 Validation Test Set - 10 Images Stratégiques

## Objectif
Tester les capacités OCR sur des cas représentatifs et critiques pour valider les claims de performance (<5s) et précision (>95%).

## Images Sélectionnées et Justifications

### 1. **MTGA deck list 4_1920x1080.jpeg**
- **Type**: MTGA Standard - Résolution HD parfaite
- **Pourquoi**: Cas idéal - devrait avoir 100% accuracy
- **Challenge**: Aucun - baseline de référence
- **Attendu**: 60 mainboard + 15 sideboard

### 2. **MTGA deck list special_1334x886.jpeg** 
- **Type**: MTGA avec effets visuels spéciaux
- **Pourquoi**: Tester robustesse avec UI modifiée
- **Challenge**: Effets visuels, résolution non-standard
- **Attendu**: Detection malgré les effets

### 3. **MTGO deck list usual_1763x791.jpeg**
- **Type**: MTGO format classique
- **Pourquoi**: Tester le MTGO land bug fix
- **Challenge**: Format texte différent de MTGA
- **Attendu**: Correction automatique des lands

### 4. **MTGO deck list not usual_2336x1098.jpeg**
- **Type**: MTGO layout inhabituel
- **Pourquoi**: Edge case MTGO
- **Challenge**: Layout non-standard, haute résolution
- **Attendu**: Adaptation au layout différent

### 5. **MTGO deck list usual 4_1254x432.jpeg**
- **Type**: MTGO basse résolution
- **Pourquoi**: Tester super-resolution (4x upscaling)
- **Challenge**: Résolution très basse (432px height)
- **Attendu**: Upscaling efficace → bonne détection

### 6. **mtggoldfish deck list 10_1239x1362.jpg**
- **Type**: MTGGoldfish website screenshot
- **Pourquoi**: Source externe populaire
- **Challenge**: Format web différent, police variable
- **Attendu**: Parsing du format web

### 7. **real deck cartes cachés_2048x1542.jpeg**
- **Type**: Cartes physiques partiellement cachées
- **Pourquoi**: Cas extrême - cartes occultées
- **Challenge**: Visibilité partielle des noms
- **Attendu**: Detection best-effort ou échec gracieux

### 8. **web site deck list_2300x2210.jpeg**
- **Type**: Site web complet avec UI
- **Pourquoi**: Extraction depuis page web complète
- **Challenge**: Beaucoup de bruit visuel, très haute résolution
- **Attendu**: Zone detection intelligente

### 9. **image_677x309.webp**
- **Type**: Très basse résolution WebP
- **Pourquoi**: Format WebP + résolution minimale
- **Challenge**: 309px height (!), format WebP
- **Attendu**: Test limite du super-resolution

### 10. **MTGA deck list_1535x728.jpeg**
- **Type**: MTGA résolution moyenne standard
- **Pourquoi**: Cas typique utilisateur moyen
- **Challenge**: Résolution commune mais pas HD
- **Attendu**: >95% accuracy sur cas standard

## Métriques à Mesurer

Pour chaque image:
1. **Temps de traitement** (cible: <5 secondes)
2. **Cartes détectées** vs attendues
3. **Accuracy** = (correctes / totales) × 100
4. **Erreurs communes** (noms mal orthographiés, cartes manquées)
5. **Sideboard detection** (15 cartes séparées)

## Critères de Succès

- ✅ **8/10 images** avec >90% accuracy
- ✅ **Temps moyen** <5 secondes
- ✅ **MTGO land fix** fonctionne
- ✅ **Super-resolution** améliore les basses résolutions
- ✅ **Pas de crash** sur cas extrêmes

## Commande de Test
```bash
cd /Volumes/DataDisk/_Projects/screen to deck
npm run test:ocr -- --dir test-images/day0-validation-set
```