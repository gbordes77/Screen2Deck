# 🚀 Screen2Deck v2.3.0 Release Notes

**Release Date**: January 21, 2025  
**Type**: Major Release - Breaking Changes

## 🎯 Executive Summary

Screen2Deck v2.3.0 marks a significant evolution in the project's architecture, transitioning from a hybrid online/offline system to a streamlined 100% ONLINE operation. This change dramatically simplifies deployment, reduces Docker image sizes by 50%, and ensures users always have access to the most current Magic: The Gathering card database.

## 🌐 Major Changes: ONLINE-ONLY Architecture

### What Changed
- **Complete removal** of all offline capabilities
- **Dynamic model loading** - EasyOCR models download on-demand
- **Direct API integration** - Scryfall API used exclusively
- **Simplified deployment** - No pre-configuration needed

### Why This Change?
1. **Simplicity**: Removed ~2000 lines of offline-specific code
2. **Maintainability**: No offline database to update/maintain
3. **Size**: Docker images reduced from ~2GB to ~1GB
4. **Accuracy**: Always current card data from Scryfall
5. **Cloud-Native**: Better suited for modern deployments

## 📦 What's New

### Features
- `make test-online` - New command for online E2E testing
- Automatic EasyOCR model download (~64MB on first use)
- Simplified Docker deployment without pre-baking

### Performance
- First request: 1-2 min (model download)
- Subsequent requests: 3-5s P95 (unchanged)
- Accuracy: 85-94% (maintained)

## 🗑️ What's Removed

### Files Deleted
- `backend/app/no_net_guard.py`
- `backend/app/routers/health_router.py` 
- `scripts/pipeline_100.sh`
- `scripts/gate_pipeline.sh`
- `PIPELINE_BULLETPROOF.md`
- All offline Scryfall database files

### Features Removed
- Air-gap mode
- Offline Scryfall database
- Pre-baked EasyOCR models
- Demo Hub (offline)
- Network isolation (No-Net Guard)

### Commands Removed
- `make pipeline-100`
- `make demo-local`
- `make validate-airgap`
- `make pack-demo`

## 🔄 Migration Guide

### Quick Migration
```bash
# 1. Pull latest code
git pull origin main

# 2. Clean old installation
docker compose down -v

# 3. Start new version
make up

# 4. Test online mode
make test-online
```

See [MIGRATION_v2.3.0.md](./MIGRATION_v2.3.0.md) for detailed instructions.

## 📊 Architecture Comparison

### Before (v2.2.x)
```
Frontend → Backend → [Offline DB + Online API Fallback] → Export
                 ↓
         [Pre-baked Models]
```

### After (v2.3.0)
```
Frontend → Backend → [Scryfall API] → Export
                 ↓
         [Download Models on-demand]
```

## ✅ Testing & Validation

All existing test suites pass with the new architecture:
- Unit tests: ✅ 100% pass
- Integration tests: ✅ 100% pass
- E2E tests: ✅ 100% pass
- Performance: ✅ Meets all SLOs

New test command:
```bash
make test-online  # Validates online operation
```

## 📚 Updated Documentation

All documentation has been updated to reflect v2.3.0:
- [README.md](./README.md) - Main documentation
- [CLAUDE.md](./CLAUDE.md) - AI assistant guide
- [HANDOFF.md](./HANDOFF.md) - Project handoff
- [TESTING.md](./TESTING.md) - Testing guide
- [ARCHITECTURE.md](./docs/ARCHITECTURE.md) - System architecture
- [DEPLOYMENT.md](./docs/DEPLOYMENT.md) - Deployment guide

## 🐛 Known Issues

1. **First run slowness**: Initial OCR request downloads models (1-2 min)
   - *Mitigation*: Models cached after first download

2. **Internet required**: System won't work without internet
   - *By design*: This is the new architecture

## 🔗 Requirements

### System Requirements
- Internet connectivity (REQUIRED)
- Docker 20.10+
- 10GB storage (reduced from 20GB)
- 4GB RAM minimum

### Network Requirements
- Access to: `api.scryfall.com`
- Access to: PyPI for model downloads
- No firewall blocking HTTPS

## 📈 Benefits

1. **50% smaller Docker images**
2. **Zero maintenance** for offline database
3. **Always current** card database
4. **Simplified deployment** process
5. **Better cloud compatibility**
6. **Reduced complexity** in codebase

## ⚠️ Breaking Changes Summary

**CRITICAL**: This version requires internet connectivity at all times. If you need offline operation, stay on v2.2.x.

## 🙏 Acknowledgments

Thanks to all contributors who helped simplify and streamline the architecture. This evolution makes Screen2Deck more maintainable and deployment-friendly.

## 📞 Support

- GitHub Issues: [Report problems](https://github.com/gbordes77/Screen2Deck/issues)
- Migration Guide: [MIGRATION_v2.3.0.md](./MIGRATION_v2.3.0.md)
- Documentation: [Full docs](./docs/)

---

**Screen2Deck v2.3.0** - Simplified. Streamlined. Online.