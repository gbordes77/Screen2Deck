# 📋 Migration Guide to v2.3.0 (ONLINE-ONLY)

## Overview

Screen2Deck v2.3.0 represents a major architectural simplification by removing all offline capabilities and transitioning to 100% online operation. This change simplifies deployment, maintenance, and ensures always-current card data.

## Breaking Changes

### 🚨 Removed Features
1. **Offline Mode**: All air-gap and offline capabilities removed
2. **Pre-baked Models**: EasyOCR models no longer included in Docker images
3. **Offline Database**: Scryfall offline database removed
4. **Demo Hub**: Local demo mode removed

### 🔄 Changed Behavior
1. **Internet Required**: System now requires internet connectivity at all times
2. **Model Download**: EasyOCR models download on first use (~64MB)
3. **Scryfall API**: All card validation now uses online API
4. **Testing**: All tests require internet connectivity

## Migration Steps

### 1. Update Your Code
```bash
# Pull latest changes
git pull origin main

# Or clone fresh
git clone https://github.com/gbordes77/Screen2Deck.git
cd Screen2Deck
```

### 2. Clean Previous Installation
```bash
# Stop and remove old containers
docker compose down -v

# Remove old images
docker rmi $(docker images | grep screen2deck | awk '{print $3}')

# Clean cache directories
rm -rf data/scryfall.sqlite
rm -rf backend/app/data/scryfall_cache.sqlite
```

### 3. Update Configuration

Remove these environment variables from your `.env` file:
```env
# REMOVE THESE:
SCRYFALL_DB=./app/data/scryfall_cache.sqlite
SCRYFALL_BULK_PATH=./app/data/scryfall-default-cards.json
AIRGAP=true
OFFLINE_MODE=true
```

Ensure these are set:
```env
# REQUIRED:
ALWAYS_VERIFY_SCRYFALL=true
ENABLE_VISION_FALLBACK=false  # Or true if you have OpenAI API key
```

### 4. Start New Version
```bash
# Start services
make up

# Or with Docker Compose
docker compose --profile core up -d

# Test online connectivity
make test-online
```

### 5. Verify Installation
```bash
# Check health
make health

# Run online test
make test-online

# Should see: "✅ Online E2E test passed!"
```

## Command Changes

### Removed Commands
| Old Command | Replacement |
|------------|-------------|
| `make pipeline-100` | `make test-online` |
| `make demo-local` | No replacement (removed) |
| `make validate-airgap` | No replacement (removed) |
| `make pack-demo` | No replacement (removed) |

### New Commands
- `make test-online` - Run online E2E validation test

## Docker Changes

### Image Size
- **Before**: ~2GB (with pre-baked models)
- **After**: ~1GB (models downloaded on-demand)

### First Run
On first OCR request, EasyOCR will download models:
- Download size: ~64MB
- Download time: 1-2 minutes (depends on connection)
- Models cached at: `~/.EasyOCR/` (in container)

## API Changes

### Endpoints
All endpoints remain the same. The only difference is that Scryfall validation always uses the online API.

### Response Times
- **First request**: May take 1-2 minutes (model download)
- **Subsequent requests**: Normal performance (3-5s P95)

## Testing Changes

### Test Requirements
All tests now require internet connectivity:
```bash
# Ensure you have internet before running tests
ping -c 1 api.scryfall.com || echo "No internet!"

# Run tests
make test
make bench-day0
make golden
make parity
```

## Troubleshooting

### Issue: "Cannot connect to Scryfall API"
**Solution**: Ensure internet connectivity and no firewall blocking

### Issue: "EasyOCR model download failed"
**Solution**: Retry the request, models will download automatically

### Issue: "Old offline tests failing"
**Solution**: Use new test commands like `make test-online`

## Benefits of v2.3.0

1. **Simplified Deployment**: No pre-configuration needed
2. **Always Current**: Real-time card database updates
3. **Smaller Images**: ~50% smaller Docker images
4. **Easier Maintenance**: No offline database to maintain
5. **Cloud-Native**: Better suited for cloud deployments

## Support

For migration issues:
1. Check this guide first
2. Review [CHANGELOG.md](./CHANGELOG.md) for all changes
3. Open an issue on GitHub with migration problems

## Rollback (if needed)

To rollback to v2.2.x:
```bash
git checkout v2.2.2
docker compose down -v
docker compose up -d
```

---

**Note**: Version 2.3.0 is a major simplification. While it removes offline capabilities, it provides a more maintainable and cloud-friendly architecture suitable for most deployment scenarios.