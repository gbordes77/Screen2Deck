# Screen2Deck — Plan de tests E2E (Playwright)
**But** : valider la reconnaissance d’images (OCR → deck) **et** l’expérience complète dans la **web app** avec preuves, métriques, et gating CI.

---

## 0) Résumé exécutable

- **Objectifs d’acceptation**
  - Accuracy moyenne ≥ **95%** (Day-20), min ≥ **92%**
  - p95 **< 5 s** (warm) / **< 8 s** (cold CI)
  - Vision fallback **< 10%** des runs courants
  - Cache hit **≥ 80%**
  - Exports **identiques** aux goldens (octet pour octet)
  - Idempotence : 10 uploads concurrents → **1 seul traitement**
- **Commandes clés**
  ```bash
  # Installation
  npm i -D @playwright/test && npx playwright install --with-deps

  # Lancer backend + webapp (exemple)
  docker compose up -d

  # Lancer la suite E2E UI
  npx playwright test --project=chromium
  npx playwright test --project=all  # chromium, firefox, webkit

  # Générer rapport HTML
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

- **Données**
  ```
  validation_set/
    day0/               # 10 images
    day20/              # +10..20 images supplémentaires (acceptance)
    adversarial/        # flou, compression, rotations, FR/EN, MTGA/MTGO/web
  golden/
    <image>.json        # deck attendu (main=60, side=15, noms exacts)
    exports/<image>/
      mtga.txt
      moxfield.txt
      archidekt.txt
      tappedout.txt
  ```

- **Env local**
  - Node 18+ / PNPM ou NPM
  - Docker (webapp + API)
  - Env vars (Playwright via `.env.e2e`):
    ```
    WEB_URL=http://localhost:3000
    API_URL=http://localhost:8080
    GOLDEN_DIR=./golden
    DATASET_DIR=./validation_set
    # Fallback (tests dédiés)
    ENABLE_VISION_FALLBACK=false
    VISION_FALLBACK_CONFIDENCE_THRESHOLD=0.62
    VISION_FALLBACK_MIN_LINES=10
    ```

---

## 3) Installation & configuration Playwright

- **Install**
  ```bash
  npm i -D @playwright/test axe-playwright
  npx playwright install --with-deps
  ```

- **`playwright.config.ts` (exemple de base)**
  ```ts
  import { defineConfig, devices } from '@playwright/test';
  export default defineConfig({
    timeout: 30_000,
    retries: 2,
    reporter: [['list'], ['junit', { outputFile: 'reports/e2e-junit.xml' }], ['html']],
    use: {
      baseURL: process.env.WEB_URL,
      trace: 'on-first-retry',
      video: 'retain-on-failure',
      screenshot: 'only-on-failure',
    },
    projects: [
      { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
      { name: 'firefox',  use: { ...devices['Desktop Firefox'] } },
      { name: 'webkit',   use: { ...devices['Desktop Safari'] } },
      { name: 'mobile',   use: { ...devices['Pixel 7'] } }
    ],
  });
  ```

- **Scripts package.json**
  ```json
  {
    "scripts": {
      "e2e": "playwright test",
      "e2e:all": "playwright test --project=all",
      "e2e:ui": "playwright test tests/web-e2e",
      "e2e:report": "playwright show-report"
    }
  }
  ```

---

## 4) Matrice de tests

- **Navigateurs** : Chromium, Firefox, WebKit
- **Viewports** : Desktop 1440×900, Mobile (Pixel 7)
- **Réseau** : normal, throttling “Slow 3G” (Playwright), offline Scryfall (route abort)
- **Jeux** : day0, day20, adversarial
- **Flags** : `ENABLE_VISION_FALLBACK=true/false`

---

## 5) Critères & métriques d’acceptation

- **Fonctionnels**
  - Deck identique aux **goldens** (noms, quantités, split main/side)
  - Exports **octet pour octet** égaux aux snapshots attendus
- **Perf UX** (mesurés via traces Playwright + WS)
  - p95 end-to-end **< 5 s** (warm), **< 8 s** (cold CI)
- **Robustesse**
  - Idempotence perçue : re-upload même fichier → réponse **instantanée**
  - Offline Scryfall : UI reste utilisable, résultat correct
  - Vision fallback : résultats **identiques** aux goldens sur cas forçables
- **Sécurité**
  - Upload refuse : non-image, magic number faux, taille/dimensions excessives
  - Aucun contenu HTML injecté depuis les données deck/cartes (anti-XSS)
- **Accessibilité**
  - Axe : pas d’erreurs critiques sur pages Upload/Deck

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
