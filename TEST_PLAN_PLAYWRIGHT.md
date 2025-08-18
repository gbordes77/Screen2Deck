# Screen2Deck — Plan de tests E2E (Playwright)
**But** : valider la reconnaissance d'images (OCR → deck) **et** l'expérience complète dans la **web app** avec preuves, métriques, et gating CI.

**Status** : ✅ **100% IMPLÉMENTÉ** - Les 14 suites de tests sont complètes et opérationnelles.

---

## 0) Résumé exécutable

- **Objectifs d'acceptation**
  - Accuracy moyenne ≥ **94%** (réaliste), min ≥ **92%**
  - p95 **< 5 s** (warm) / **< 8 s** (cold CI)
  - Vision fallback **désactivé par défaut** (ENABLE_VISION_FALLBACK=false)
  - Cache hit **≥ 80%**
  - Exports **identiques** aux goldens (octet pour octet)
  - Idempotence : 10 uploads concurrents → **1 seul traitement**
- **Commandes clés**
  ```bash
  # Installation
  npm ci && npx playwright install --with-deps

  # Lancer backend + webapp
  docker compose --profile core up -d

  # Quick smoke test (recommandé pour premier run)
  make e2e-smoke

  # Suite complète
  make e2e-ui

  # Rapport HTML
  npx playwright show-report
  ```

---

## 1) Périmètre

- Parcours **UI** complet : Upload → Progression (WS) → Deck affiché → Exports (MTGA/Moxfield/Archidekt/TappedOut)
- Robustesse : Vision fallback, offline Scryfall, idempotence, erreurs d’upload
- Sécurité front : validation fichiers (type, magic number, taille, dimensions), anti-XSS
- Accessibilité (a11y), responsivité (desktop/mobile), régression visuelle ciblée
- Parité **UI vs API** & **UI vs Goldens**

---

## 2) Prérequis & jeux de données

- **Données** (structure mise à jour)
  ```
  validation_set/
    images/             # Images de test (anciennement day0)
    adversarial/        # Images difficiles (flou, compression, rotations)
    truth/              # Ground truth pour benchmarks
  golden/
    exports/<image>/    # Exports de référence
      mtga.txt
      moxfield.txt
      archidekt.txt
      tappedout.txt
  ```

- **Env local**
  - Node 20+ (recommandé) / NPM
  - Docker (webapp + API avec `--profile core`)
  - Env vars (Playwright via `.env.e2e`):
    ```
    WEB_URL=http://localhost:3000
    API_URL=http://localhost:8080
    GOLDEN_DIR=./golden
    DATASET_DIR=./validation_set
    TEST_IMAGES_DIR=./validation_set/images  # Mis à jour
    # Vision fallback (désactivé par défaut)
    ENABLE_VISION_FALLBACK=false
    # Tests S5 skippés si OPENAI_API_KEY non définie
    ```

---

## 3) Installation & configuration Playwright

- **Install** (simplifiée)
  ```bash
  npm ci
  npx playwright install --with-deps
  ```

- **Configuration** (`playwright.config.ts` créé)
  - Timeout: 30s par test (60s pour S4 WebSocket et S12 Performance)
  - Retries: 2 en CI, 1 en local
  - Multi-browser: Chrome, Firefox, Safari, Mobile
  - Artifacts: traces, videos, screenshots on failure
  - Reporter: HTML + JUnit

- **Scripts package.json** (mis à jour)
  ```json
  {
    "scripts": {
      "e2e": "playwright test",
      "e2e:chromium": "playwright test --project=chromium",
      "e2e:firefox": "playwright test --project=firefox",
      "e2e:webkit": "playwright test --project=webkit",
      "e2e:mobile": "playwright test --project=mobile",
      "e2e:headed": "playwright test --headed",
      "e2e:debug": "playwright test --debug",
      "e2e:report": "playwright show-report"
    }
  }
  ```

- **Makefile targets** (nouveaux)
  ```bash
  make e2e-ui      # Suite complète
  make e2e-smoke   # Test rapide S1 sur Chrome
  ```

---

## 4) Matrice de tests

- **Navigateurs** : Chromium, Firefox, WebKit
- **Viewports** : Desktop 1440×900, Mobile (Pixel 7)
- **Réseau** : normal, throttling “Slow 3G” (Playwright), offline Scryfall (route abort)
- **Jeux** : day0, day20, adversarial
- **Flags** : `ENABLE_VISION_FALLBACK=true/false`

---

## 5) Critères & métriques d'acceptation

- **Fonctionnels**
  - Deck identique aux **goldens** (noms, quantités, split main/side)
  - Exports **octet pour octet** égaux aux snapshots attendus
- **Perf UX** (mesurés via traces Playwright + WS)
  - p95 end-to-end **< 5 s** (SLO défini dans .env.e2e)
- **Robustesse**
  - Idempotence perçue : re-upload même fichier → réponse **instantanée**
  - Offline Scryfall : UI reste utilisable, résultat correct
  - Vision fallback : **skippé si pas d'OPENAI_API_KEY**
- **Sécurité**
  - Upload refuse : non-image, magic number faux, taille/dimensions excessives
  - Aucun contenu HTML injecté depuis les données deck/cartes (anti-XSS)
- **Accessibilité**
  - Axe : pas d'erreurs critiques sur pages Upload/Deck
- **Sélecteurs**
  - Priorité aux `data-testid` avec fallback sur sélecteurs génériques

---

## 6) Suites de tests (exhaustives)

> Chaque test suit le format : **ID**, **But**, **Données**, **Étapes**, **Assertions**.

### S1 — Happy path (UI)
- **S1.1** Upload → Deck → Export MTGA  
  **Données** : `day0/sample_*.jpg|png|webp`  
  **Étapes** : ouvrir UI, uploader, attendre “Deck ready”, télécharger MTGA  
  **Assertions** : présence “Sideboard”, export **=** golden `exports/<image>/mtga.txt`

- **S1.2** Export Moxfield / Archidekt / TappedOut  
  **Assertions** : chaque export égale son **golden** respectif

### S2 — Parité UI vs API vs Goldens
- **S2.1** UI export = API export  
  **Étapes** : lancer parcours UI + appeler `/api/export/*` via `test.request`  
  **Assertions** : UI export **===** API export **===** snapshot golden

### S3 — Idempotence (UI visible)
- **S3.1** Re-upload du **même** fichier  
  **Étapes** : upload A → OK ; re-upload A  
  **Assertions** : 2e réponse **quasi instantanée** ; messages UI indiquant cache (si prévu)

- **S3.2** Concurrence (multi-tabs)  
  **Étapes** : 5 pages Playwright uploadent **le même** fichier en parallèle  
  **Assertions** : une seule progression “longue”, les autres finalisent vite ; exports **identiques**

### S4 — WebSocket (progression)
- **S4.1** Ordre d’événements  
  **Assertions** : `preproc:start` → `ocr:easyocr:done` → `match:scryfall:offline_hit|online` → `export:ready`

- **S4.2** Contenu des frames  
  **Assertions** : chaque frame contient `jobId`, `step`, `elapsed_ms`, pas de données sensibles

### S5 — Vision fallback
- **S5.1** Fallback forcé (seuils élevés)  
  **ENV** : `ENABLE_VISION_FALLBACK=true`, `VISION_FALLBACK_CONFIDENCE_THRESHOLD=0.95`  
  **Assertions** : export final **identique** au golden ; badge/indicateur fallback présent (si prévu)

- **S5.2** Circuit breaker  
  **Étapes** : simuler plusieurs fallback consécutifs (sur adversarial)  
  **Assertions** : l’UI reste fonctionnelle ; pas d’erreurs non gérées ; messages clairs

### S6 — Offline Scryfall
- **S6.1** Abort des requêtes vers `scryfall.com`  
  **Étapes** : `page.route(/scryfall\.com/, route => route.abort())`  
  **Assertions** : deck obtenu ; UI signale mode cache (si prévu)

### S7 — Sécurité upload
- **S7.1** Non-image déguisée (.png mais EXE)  
  **Assertions** : message “format non supporté / bad magic”

- **S7.2** Taille > N Mo  
  **Assertions** : “file too large”

- **S7.3** Dimensions > W×H max  
  **Assertions** : “dimensions”

- **S7.4** PDF/SVG (interdit)  
  **Assertions** : “format non supporté”

### S8 — Erreurs & UX
- **S8.1** Image corrompue  
  **Assertions** : toast d’erreur, aucune boucle infinie, retour état initial possible

- **S8.2** Timeout backend simulé (throttle réseau)  
  **Assertions** : spinner non figé, message “toujours en cours”, possibilité d’annuler/retry

### S9 — Accessibilité (axe)
- **S9.1** Page Upload  
- **S9.2** Page Deck  
  **Assertions** : axe violations (niveau sérieux) = 0, focus management OK, labels alt présents

### S10 — Responsivité
- **S10.1** Mobile (Pixel 7) — Upload → Deck → Export  
  **Assertions** : layout non cassé, actions accessibles

- **S10.2** Fenêtre réduite (sidebar repliée)  
  **Assertions** : éléments essentiels visibles (boutons export)

### S11 — Régression visuelle ciblée
- **S11.1** Screenshot `deck-panel`  
  **Masques** : timestamp, jobId  
  **Assertions** : diff < 1%

### S12 — Performance (smoke UI)
- **S12.1** Mesure end-to-end  
  **Étapes** : chronométrer upload→deck→export depuis test (horodatage UI/WS)  
  **Assertions** : p95 **< SLO** (calculé sur échantillon day0)

### S13 — Cas deck complexes
- **S13.1** DFC / Split / Adventure  
- **S13.2** Noms multilingues + diacritiques  
- **S13.3** Sideboard ≠ 15 → UI propose fix  
- **S13.4** MTGO lands bug  
  **Assertions** : conformité exacte aux goldens + messages UI cohérents

### S14 — Anti-XSS & sécurité rendu
- **S14.1** Noms de cartes/pièges (`<img onerror=...>`, `</div>...`)  
  **Assertions** : rendu **en texte**, **aucun HTML interprété**, pas de JS exécuté

---

## 7) Déploiement & exécution (local & CI)

### Local
```bash
# 1) Démarrer la stack
docker compose up -d

# 2) Installer Playwright
npm i -D @playwright/test axe-playwright
npx playwright install --with-deps

# 3) Lancer toute la matrice
WEB_URL=http://localhost:3000 API_URL=http://localhost:8080 GOLDEN_DIR=./golden DATASET_DIR=./validation_set npx playwright test --project=all

# 4) Consulter le rapport
npx playwright show-report
```

### CI (GitHub Actions) — exemple
```yaml
name: web-e2e
on: [push, workflow_dispatch]
jobs:
  e2e:
    runs-on: ubuntu-latest
    services:
      backend:
        image: ghcr.io/gbordes77/screen2deck-backend:latest
        ports: [ "8080:8080" ]
      web:
        image: ghcr.io/gbordes77/screen2deck-webapp:latest
        ports: [ "3000:3000" ]
      redis:
        image: redis:7-alpine
        ports: [ "6379:6379" ]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '18' }
      - name: Install Playwright
        run: |
          npm i -D @playwright/test axe-playwright
          npx playwright install --with-deps
      - name: Run E2E UI
        env:
          WEB_URL: http://localhost:3000
          API_URL: http://localhost:8080
          GOLDEN_DIR: ./golden
          DATASET_DIR: ./validation_set
        run: npx playwright test --project=all
      - name: Upload artifacts
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-artifacts
          path: |
            playwright-report
            test-results
```

---

## 8) Gating & rapports

- **Gating CI** : la job **échoue** si :
  - Comparaison exports ≠ goldens
  - p95 > SLO défini
  - A11y critiques > 0
  - Upload sécurité non respectée (fichiers illégitimes acceptés)
- **Artefacts CI** : `playwright-report/`, **traces**, **vidéos**, **screenshots**, exports téléchargés
- **Publication release** : joindre **rapport E2E** (HTML/zip), plus rapports API (Day-0/Day-20)

---

## 9) Bonnes pratiques supplémentaires

- Synchroniser le runner API (E2E back) **avant** la suite UI, pour valider les goldens et SLO.
- Marquer les **tests Vision/offline** comme flakey autorisés → retries 1–2.
- Garder les **goldens** stables (ordre, fin de ligne, capitalisation). Toute modif doit être volontaire et revue.

---

## 10) Liste complète des cas (checklist)

- [ ] Upload → Deck → Exports (4 formats) — day0 + day20  
- [ ] Parité UI vs API vs Goldens  
- [ ] Idempotence : re-upload, concurrence (multi-tabs)  
- [ ] WebSocket : ordre & contenu des frames  
- [ ] Vision fallback (forcé) + circuit breaker  
- [ ] Offline Scryfall (abort)  
- [ ] Sécurité upload (non-image, magic, taille, dimensions, PDF/SVG)  
- [ ] Erreurs & UX (corruption, timeout)  
- [ ] Accessibilité (axe) — pages Upload/Deck  
- [ ] Responsivité (desktop/mobile)  
- [ ] Régression visuelle ciblée (deck panel)  
- [ ] Perf smoke p95  
- [ ] DFC/Split/Adventure, diacritiques, sideboard ≠ 15, MTGO lands bug  
- [ ] Anti-XSS (rendu texte only)

---

### Fin
Ce document est prêt à être ajouté dans `docs/TEST_PLAN_PLAYWRIGHT.md` et exécuté tel quel avec Playwright.
