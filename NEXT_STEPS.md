# Screen2Deck — Ce qu'il te reste à faire

> Feuille de route opérationnelle après la session 2026-04-14.
> Organisée par priorité : les items rouges bloquent la mise en œuvre,
> les oranges la finalisent, les jaunes sont de la dette technique
> trackée. Chaque item a une commande exacte et un critère de succès.

**Date de dernière mise à jour** : 2026-04-14
**Branche de travail** : `refactor/consolidation-2026-04-14`
**PR** : https://github.com/gbordes77/Screen2Deck/pull/2

---

## 🔴 BLOQUANTS — faire avant de pouvoir lancer le projet

Ces 5 items sont la séquence minimale pour passer de "code sur une
branche" à "stack qui tourne sur ma machine".

### 1. Remplir `.env` avec les 2 secrets manquants

**Durée** : 30 secondes

```bash
cd /Volumes/DataDisk/_Projects/Screen2Deck

# Générer les 2 secrets (Mac ou Linux)
POSTGRES_PASSWORD_VALUE=$(openssl rand -hex 16)
JWT_SECRET_KEY_VALUE=$(openssl rand -base64 32)

# Les écrire dans .env (remplace les lignes vides existantes)
sed -i.bak "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD_VALUE}|" .env
sed -i.bak "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${JWT_SECRET_KEY_VALUE}|" .env
rm .env.bak
```

**Vérification** :
```bash
grep -E "^(POSTGRES_PASSWORD|JWT_SECRET_KEY|GEMINI_API_KEY)=" .env
# → 3 lignes, toutes remplies
```

**État actuel** : `GEMINI_API_KEY=AIzaSy...` déjà collée. Les 2 autres sont vides.

---

### 2. Pré-hydrater le cache Scryfall

**Durée** : 1–3 min (selon ta bande passante, télécharge ~150 MB)

```bash
python backend/scripts/download_scryfall.py
```

**Vérification** :
```bash
ls -lh backend/app/data/scryfall-default-cards.json
# → doit exister, ~120-180 MB
```

**Pourquoi c'est bloquant-ish** : sans ça, chaque upload tape l'endpoint
online de Scryfall qui est rate-limité à 10 req/s. Les premiers tests
vont être lents et peuvent échouer. Avec le bulk hydrate, la résolution
se fait en mémoire et le test tourne en < 3 s.

**Si ça crash** : probablement un problème d'import. Le script a été
réécrit dans cette session pour être importable depuis n'importe quel
cwd, mais jamais testé réellement. Flag à surveiller.

---

### 3. Lancer le smoke test end-to-end

**Durée** : 3–6 min (premier `docker compose build` inclus)

```bash
make smoke
```

Le script `tests/smoke_test.sh` fait, dans l'ordre :
1. Préflight (binaires, env vars, image de test)
2. `make up` — boot du stack complet
3. Attend `/health` (timeout 180 s)
4. Upload d'une image de `validation_set/images/`
5. Poll `/api/ocr/status/:id` jusqu'à `completed` (timeout 120 s)
6. Vérifie que le deck a ≥20 cartes main et ≥50 % résolues via Scryfall
7. Affiche les 5 premières cartes pour inspection visuelle
8. Exerce l'endpoint `/api/export/mtga`

**Critère de succès** : le script sort `[✓] ALL CHECKS PASSED` et le
stack reste up pour que tu puisses poker dessus.

**Si ça échoue** :
- Le script dump automatiquement les 80 dernières lignes de
  `docker compose logs backend`
- Regarde le step qui a foiré (l'output est coloré)
- Les cas les plus probables :
  - `make up` → problème de dépendances Docker (google-genai / anthropic
    / PyJWT peuvent avoir des conflits transitifs — non vérifié dans la session)
  - `/health` timeout → le backend crash au boot, lis les logs
  - Upload OK mais job failed → un import Python a cassé, probablement
    dans `vision_providers.py` ou `auth_router.py`
  - Résolution Scryfall < 50 % → le bulk hydrate n'a pas fonctionné,
    ou le User-Agent header ne passe pas

**Confiance après vert** : passe de ~55 % à ~85 % sur "le projet fait
ce qui est décrit dans how-it-works.html".

---

### 4. Vérifier que la PR #2 a au moins `e2e-online` vert

**Durée** : variable (0 s si déjà vert, plusieurs minutes si CI repart)

```bash
gh pr checks 2 | grep -E "e2e-online|Test Backend|Test Frontend"
```

**Critère de succès** : les 3 lignes disent `pass` ou `success`.

**État attendu au moment d'écrire ce fichier** :
- `Test Backend` : SUCCESS (confirmé dans la dernière check CI)
- `Test Frontend` : SUCCESS (confirmé)
- `e2e-online` : probablement vert ou en cours — le dernier fix
  (`98445f7` sur `docker-compose.yml env_file: required: false`) a été
  poussé en fin de session et je n'ai pas attendu son résultat

**Si `e2e-online` est rouge** :
```bash
# Trouver le dernier run
gh run list --workflow=e2e-online.yml --branch refactor/consolidation-2026-04-14 --limit 1

# Voir la cause
gh run view <ID> --log-failed | head -40
```
Les causes probables, dans l'ordre de vraisemblance :
1. Un `env_file: required: false` mal parsé par l'ancienne version de
   Docker Compose installée sur le runner → fallback : retirer l'entrée
   `env_file` complètement et tout mettre en `environment:`
2. Le backend crash au boot sur un import Vision — la doc de l'agent
   OCR-research pourrait avoir donné une mauvaise signature google-genai
3. Quota Gemini free tier déjà consommé par d'autres tests

---

### 5. Merger la PR

**Durée** : 10 secondes

```bash
gh pr merge 2 --squash --delete-branch
```

**Critère de succès** : la PR passe à `merged`, `main` gagne 32 commits
en squash, la branche `refactor/consolidation-2026-04-14` disparaît
localement et sur origin.

**Pré-requis** :
- Items 1–4 complétés
- Tu es OK avec un squash (alternative : `--merge` pour garder les
  commits individuels, utile si tu veux bisect plus tard)

---

## 🟠 IMPORTANT — à faire dans les jours qui suivent le merge

### 6. Lancer un vrai benchmark et mettre à jour `DISCLAIMER.md`

**Durée** : 10–30 min selon la taille du `validation_set/`

```bash
make bench-day0
# ou directement :
python tools/benchmark.py --images validation_set/images --out reports/day0.json
```

Ça produit un JSON avec les vraies p50/p95 mesurées, l'accuracy par
image, le coût par appel. Ensuite éditer `DISCLAIMER.md` pour faire
passer ces items de la colonne "⚠️ Projected" à "✅ Verified".

**Pourquoi c'est important** : tant que les chiffres du README et de
`how-it-works.html` sont des projections, n'importe qui peut les
contester. Une fois mesurés, c'est défendable.

### 7. Faire un smoke test sur le **chemin legacy** aussi

```bash
# Flip Vision-primary off temporairement
VISION_PRIMARY=false make smoke
```

Vérifie que le chemin EasyOCR fallback tourne encore (important : c'est
le filet de sécurité si Gemini est down ou quota épuisé).

### 8. Tester l'upload d'un vrai screenshot MTGO

L'image `validation_set/images/MTGO deck list usual_1763x791.jpeg` est
un bon candidat. C'est le cas où `apply_mtgo_land_fix` doit redécouper
60+15 — logique réécrite dans cette session mais jamais exercée.

```bash
curl -X POST http://localhost:8080/api/ocr/upload \
  -F "file=@validation_set/images/MTGO deck list usual_1763x791.jpeg"
# → {jobId}

curl http://localhost:8080/api/ocr/status/<JOBID>
# → vérifier que main + side font bien 60 + 15 dans normalized
```

### 9. Rotation des secrets locaux

Tu as déjà révoqué la clé OpenAI. Vérifie également que :
- Le `POSTGRES_PASSWORD` généré au step 1 est unique (pas le même que
  sur un autre projet)
- Le `JWT_SECRET_KEY` est unique (pas réutilisé)
- `GEMINI_API_KEY` — si tu as un doute sur son exposition, regénère-la
  sur aistudio.google.com/app/apikey (5 secondes)

### 10. Ouvrir `docs/how-it-works.html` dans ton navigateur et le lire

Sérieusement. Tu l'as déjà vu passer dans Brave, mais relis-la
maintenant qu'elle a les badges `projeté` / `vérifié`. Si tu trouves
une incohérence ou une explication qui ne matche pas le vrai code,
signale-le — c'est le moment d'amender avant que quelqu'un d'externe
la découvre.

---

## 🟡 DETTE TECHNIQUE trackée — à faire quand tu as du temps

Ces items sont documentés dans les audits multi-agents et dans
`DISCLAIMER.md`. Ils ne bloquent pas la mise en œuvre mais mériteraient
chacun leur propre PR.

### 11. Formatting pass + re-activer `Lint Code` gating

Actuellement `Lint Code` est en `continue-on-error: true`. Pour le
remettre en gating :

```bash
pip install black ruff
black backend/
ruff check --fix backend/
git add -u && git commit -m "style: black + ruff pass"
# Puis éditer .github/workflows/ci.yml pour retirer continue-on-error
```

### 12. Alembic — migration initiale

Aujourd'hui le schéma PostgreSQL est créé par
`Base.metadata.create_all()` au startup. Zéro historique de migration
= impossible de faire évoluer le schéma en prod sans downtime.

```bash
cd backend
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
git add alembic/versions/
```

### 13. Supprimer les fichiers non trackés à la racine

Ces fichiers traînent depuis le début de la session, marqués
`untracked` par `git status` :
- `OCR_ANALYSIS_REPORT.html`
- `PROJECT_INDEX.md`
- `PR_BODY.md`
- `UAT_GUIDE.html`
- `analyze_validation_images.py`, `test_improved_ocr.py`,
  `test_ocr_raw.py`, `test_parse_logic.py`
- `server_working_backup/` (tout le dossier legacy)
- `validation_set/imported_from_old_project/` (origine légale non documentée)

```bash
# Vérifier avant de supprimer
git status --short | grep "^??"

# Supprimer si tu es sûr
rm -rf server_working_backup
rm OCR_ANALYSIS_REPORT.html PROJECT_INDEX.md PR_BODY.md UAT_GUIDE.html
rm analyze_validation_images.py test_*.py
# Attention : validation_set/imported_from_old_project peut contenir
# des images utilisables — vérifier le contenu avant suppression
```

### 14. Supprimer `PROOF_SUMMARY.md` (flagué comme redondant)

L'audit documentation a dit que ce fichier fait doublon avec
`README.md`. Si tu es d'accord :
```bash
git rm PROOF_SUMMARY.md
```

### 15. Ajouter ESLint au webapp

Aujourd'hui `npm run lint` est un no-op. Pour un vrai linting :
```bash
cd webapp
npm install --save-dev eslint-config-next@14.2.5 eslint@8
cat > .eslintrc.json <<'EOF'
{
  "extends": "next/core-web-vitals"
}
EOF
# Éditer package.json "lint": "next lint"
```

### 16. Cache Redis par hash SHA-256 de l'image

Aujourd'hui l'idempotency check existe mais la TTL est courte (24 h).
Un cache 30 jours par image hash permettrait de diviser les appels
Gemini par ~50 % en pratique (les mêmes screenshots circulent). Voir
`backend/app/core/job_storage.py` pour l'implémentation actuelle.

### 17. OpenTelemetry spans per-stage

Dans `main.py::process_ocr`, il n'y a qu'un span global
`process_ocr`. Pour débugger les régressions p95 en prod, il faut des
spans enfants : `preprocess`, `ocr`, `vision_fallback`, `scryfall`,
`parse`, `normalize`, `export`. 20 lignes à ajouter.

### 18. Valider la syntaxe exacte des SDK Vision

Les 3 points d'incertitude les plus probables (cf `DISCLAIMER.md`) :
1. `google-genai` : `types.GenerateContentConfig(response_mime_type=..., response_schema=...)`
2. `anthropic` : `tool_choice={"type":"tool","name":"return_deck"}`
3. Docker Compose : `env_file: [{path: ..., required: false}]`

Pour chacun, un test runtime suffit à confirmer. Le cas #3 est déjà
couvert par le smoke test ; les cas #1 et #2 ne sont exercés qu'une
fois que tu fais un vrai upload qui déclenche Vision-primary.

### 19. ESO / Sealed Secrets pour la prod

Si tu déploies ailleurs que sur ton laptop, les `__REPLACE_ME__` dans
`k8s/secrets.yaml` doivent être remplacés par un vrai système de
gestion de secrets. Options :
- External Secrets Operator + AWS Secrets Manager / Vault / GCP SM
- Sealed Secrets de Bitnami (blob chiffré checkable dans git)
- Injection via CI pipeline au moment du `kubectl apply`

### 20. Backups PostgreSQL

Le `StatefulSet` Postgres dans `k8s/` tourne avec `replicas: 1` et
zéro stratégie de backup. Un redémarrage hard du pod = perte totale.
Options :
- CronJob nightly `pg_dump` vers S3
- CloudNativePG / Zalando operator avec PITR
- Pour le dev local, `docker compose exec postgres pg_dump` suffit

### 21. Grafana dashboards + SLO alerts

Le backend expose déjà `/metrics` (Prometheus). Ce qui manque :
- Scrape config Prometheus
- Dashboards Grafana (latency p50/p95, cache hit rate, Scryfall lookup
  source distribution, Vision fallback rate)
- Alert rules sur les budgets (Gemini API cost daily, p95 > 5 s, 5xx
  rate)

### 22. Tests unitaires réels sur les parties critiques

Les 2 tests ajoutés (`test_business_rules.py`, `test_exporters.py`)
sont un début. Ce qui manque pour prétendre à une couverture >70 % :
- `test_vision_providers.py` — mocks google-genai / anthropic et
  vérifie le fallback chain
- `test_scryfall_client.py` — mocks `requests.post` pour
  `/cards/collection` et vérifie la face reconciliation split/DFC
- `test_main_process_ocr.py` — mocks les deux code paths et vérifie
  que VISION_PRIMARY=true prend bien le bon branch
- `test_auth.py` — vérifie que get_optional_token retourne None sans
  header mais TokenData avec un vrai JWT

### 23. Tests E2E Playwright VISION_PRIMARY

Les 14 suites Playwright existantes n'ont jamais été écrites contre le
chemin Vision-primary (qui n'existait pas). Une nouvelle suite dédiée :
- Upload d'un screenshot MTGA
- Vérifier que les logs backend tracent `ocr.method=vision_gemini_structured`
- Vérifier que le résultat affiché dans la webapp est cohérent

---

## 🔵 À NE PAS FAIRE / décisions archivées

Ces choix ont été débattus pendant la session et tranchés. Ne les
rouvre pas sans raison :

- **Ne pas rajouter OpenAI Vision** — migré vers Gemini/Claude
  intentionnellement. L'ancienne clé est révoquée.
- **Ne pas réutiliser python-jose** — CVE-2024-33663 / 33664. PyJWT est
  le remplaçant définitif.
- **Ne pas supprimer `scryfall_client.py`** malgré ce qu'ont dit 2 agents
  de l'audit initial. Il est utilisé par `main.py::normalize_deck` et
  par `scripts/download_scryfall.py`. L'agent avait confondu avec
  `scryfall_cache.py` (qui a bien été supprimé).
- **Ne pas repasser à `gemini-2.5-flash`** — 3.1-flash-lite-preview est
  strictement supérieur sur tous les axes (prix, vitesse, intelligence).
- **Ne pas découpler Celery en retry** — la tentative initiale a produit
  un `tasks.py` avec une regex double-escaped cassée qui n'a jamais
  matché. Le chemin inline dans `main.py::process_ocr` est suffisant
  au volume actuel.

---

## 📋 Checklist de mise en œuvre (à cocher au fur et à mesure)

Minimum pour lancer :
- [ ] Step 1 — `.env` rempli (POSTGRES_PASSWORD, JWT_SECRET_KEY)
- [ ] Step 2 — `python backend/scripts/download_scryfall.py` exécuté
- [ ] Step 3 — `make smoke` vert
- [ ] Step 4 — `gh pr checks 2` avec `e2e-online` vert
- [ ] Step 5 — `gh pr merge 2 --squash --delete-branch`

Finalisation (dans les jours qui suivent) :
- [ ] Step 6 — `make bench-day0` tourné, DISCLAIMER.md mis à jour
- [ ] Step 7 — Smoke test legacy path (`VISION_PRIMARY=false make smoke`)
- [ ] Step 8 — Upload MTGO vérifié (`apply_mtgo_land_fix` marche)
- [ ] Step 9 — Rotation secrets locaux confirmée
- [ ] Step 10 — `how-it-works.html` relue

Dette technique (quand tu as du temps) :
- [ ] Step 11 — Formatting pass + Lint Code regating
- [ ] Step 12 — Alembic migration initiale
- [ ] Step 13 — Cleanup fichiers untracked
- [ ] Step 14 — Suppression PROOF_SUMMARY.md
- [ ] Step 15 — ESLint sur webapp
- [ ] Step 16 — Cache Redis par image hash
- [ ] Step 17 — OpenTelemetry spans per-stage
- [ ] Step 18 — Validation syntax SDK Vision
- [ ] Step 19 — ESO / Sealed Secrets k8s
- [ ] Step 20 — Backups PostgreSQL
- [ ] Step 21 — Grafana + SLO alerts
- [ ] Step 22 — Tests unitaires critiques
- [ ] Step 23 — Tests E2E VISION_PRIMARY

---

## 🆘 Plan de rollback

Si quelque chose tourne mal après le merge :

```bash
# 1. Revenir au commit juste avant le merge
git log --oneline main | head -5
git revert <merge-commit-hash>
git push origin main

# 2. OU désactiver Vision primary sans revert
# Dans .env ou les vars d'env de prod :
VISION_PRIMARY=false
ENABLE_VISION_FALLBACK=false
# Le stack retombe intégralement sur EasyOCR (comportement v2.3.0)

# 3. OU désactiver juste Vision mais garder tout le reste
VISION_PRIMARY=false
# EasyOCR primary + Vision en fallback sur low-confidence (comportement de transition)
```

Le vieux comportement EasyOCR est 100 % préservé — le flag
`VISION_PRIMARY=false` rentre dans le code path qui était le chemin
par défaut de v2.3.0, et qui est toujours présent dans `main.py`.

---

## 📚 Liens utiles

- **PR** : https://github.com/gbordes77/Screen2Deck/pull/2
- **Doc architecture** : [`docs/how-it-works.html`](./docs/how-it-works.html)
- **Status des claims** : [`DISCLAIMER.md`](./DISCLAIMER.md)
- **Session notes** : [`SESSION_NOTES.md`](./SESSION_NOTES.md)
- **CHANGELOG** : [`CHANGELOG.md`](./CHANGELOG.md)
- **Smoke test** : [`tests/smoke_test.sh`](./tests/smoke_test.sh)
- **Makefile targets** : `make help`
- **Scryfall rate limits** : https://scryfall.com/docs/api/rate-limits
- **Gemini API docs** : https://ai.google.dev/gemini-api/docs
- **Anthropic API docs** : https://docs.anthropic.com

---

**TL;DR** : Steps 1→5 prennent ~10 min total. Si `make smoke` passe
vert au step 3, tout le reste est du polish trackable à ton rythme.
