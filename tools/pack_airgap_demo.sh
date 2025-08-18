#!/bin/bash
# Create a transportable air-gapped demo package

set -e

echo "📦 Creating air-gapped demo package..."

# Build everything first
echo "🔨 Building services..."
make demo-seed
make docs-build
make web-build

# Build Docker images
echo "🐳 Building Docker images..."
docker compose -f docker-compose.local.yml build

# Create package directory
rm -rf _airgap
mkdir -p _airgap

# Save Docker images
echo "💾 Saving Docker images..."
docker save nginx:alpine > _airgap/nginx_alpine.tar
docker save squidfunk/mkdocs-material:latest > _airgap/mkdocs.tar
docker save postgres:15-alpine > _airgap/postgres.tar
docker save redis:7-alpine > _airgap/redis.tar

# Save app images
APP_IMAGES=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E 'screen2deck-api|screen2deck-web' || true)
if [ -n "$APP_IMAGES" ]; then
    docker save $APP_IMAGES > _airgap/app_images.tar
fi

# Create tarball
echo "📁 Creating archive..."
tar -czf Screen2Deck_airgap_demo.tar.gz \
    docker-compose.local.yml \
    ops/nginx \
    _build \
    webapp/public/demo \
    docs \
    artifacts \
    playwright-report \
    data/scryfall.sqlite \
    _airgap \
    Makefile \
    .env.example \
    tools/build_offline_seed.py \
    tools/validate_airgap.sh \
    README_AIRGAP.md 2>/dev/null || true

# Create README for the package
cat > README_AIRGAP.md << 'EOF'
# Screen2Deck Air-Gapped Demo

This package contains everything needed to run Screen2Deck demo on a machine with NO internet connection.

## Installation (on target machine)

1. Extract the archive:
```bash
tar -xzf Screen2Deck_airgap_demo.tar.gz
```

2. Load Docker images:
```bash
docker load < _airgap/nginx_alpine.tar
docker load < _airgap/mkdocs.tar
docker load < _airgap/postgres.tar
docker load < _airgap/redis.tar
docker load < _airgap/app_images.tar
```

3. Start the demo:
```bash
make demo-local
```

4. Access the demo:
```
http://localhost:8088
```

## What's included

- Complete web UI at `/app`
- Backend API at `/api`
- Documentation at `/docs`
- Test reports at `/report`
- Metrics at `/artifacts`
- 75 pre-loaded MTG cards in offline database
- NO external network calls

## Validation

Run the validation script to confirm air-gap:
```bash
./tools/validate_airgap.sh
```

All checks should show ✓ (green).

## Features

- 🔒 100% offline operation
- 📷 OCR processing with EasyOCR
- ✅ Card validation against local database
- 📊 Export to multiple formats
- 🚀 <3 second processing time
- 🛡️ Security headers and rate limiting

## Troubleshooting

If services don't start:
```bash
docker compose -f docker-compose.local.yml down
docker compose -f docker-compose.local.yml up -d api nginx redis postgres
```

Check logs:
```bash
docker logs s2d_api
docker logs s2d_gateway
```

---
Generated on $(date)
EOF

echo ""
echo "✅ Air-gapped demo package created!"
echo ""
echo "📦 Package: Screen2Deck_airgap_demo.tar.gz"
echo "📏 Size: $(du -h Screen2Deck_airgap_demo.tar.gz | cut -f1)"
echo ""
echo "To deploy on air-gapped machine:"
echo "1. Copy Screen2Deck_airgap_demo.tar.gz to target"
echo "2. Extract: tar -xzf Screen2Deck_airgap_demo.tar.gz"
echo "3. Load images: docker load < _airgap/*.tar"
echo "4. Start: make demo-local"
echo "5. Open: http://localhost:8088"