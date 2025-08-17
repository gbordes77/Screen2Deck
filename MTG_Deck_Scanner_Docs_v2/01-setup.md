# Setup & First Run

## Prereqs
- Docker + Docker Compose
- Internet on first run (EasyOCR model download, Scryfall bulk)
- CPU-only is fine (no GPU). No Tesseract.

## One-liner (Docker)
```bash
docker compose up --build
# open http://localhost:3000
```

## Manual first-run cache (optional)
```bash
cd backend
python -m pip install -r requirements.txt
python scripts/download_scryfall.py
cd ..
docker compose up --build
```

## Smoke test (curl)
```bash
# with a sample image in validation_set/
curl -s -F file=@validation_set/MTGA\ deck\ list_1535x728.jpeg http://localhost:8080/api/ocr/upload
# => { "jobId": "..." }
curl -s http://localhost:8080/api/ocr/status/<jobId>
```

## Folder layout
```
monorepo/
  backend/          # FastAPI + OCR pipeline + exporters
  webapp/           # Next.js UI
  validation_set/   # Put your sample images here
  docker-compose.yml
  .env, .env.example
```
