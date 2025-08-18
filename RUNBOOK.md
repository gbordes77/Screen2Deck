# 🚨 Screen2Deck Runbook - Troubleshooting Guide

## Quick Diagnostics

### 🔴 System Down
```bash
# 1. Check all services
docker compose ps

# 2. Check health
curl -f http://localhost:8080/health || echo "API DOWN"

# 3. View logs
docker compose logs --tail=50 backend

# 4. Restart
docker compose restart backend
```

---

## Common Issues & Solutions

### 1. 📉 Accuracy Drop (<40%)

**Symptoms**: OCR returning wrong cards, low confidence scores

**Diagnosis**:
```bash
# Check OCR engine
docker compose exec backend python -c "from app.config import settings; print(f'Engine: easyocr, Vision: {settings.ENABLE_VISION_FALLBACK}')"

# Test with known good image
curl -X POST http://localhost:8080/api/ocr/upload \
  -F "file=@validation_set/MTGA deck list_1535x728.jpeg" | jq .
```

**Solutions**:
1. ✅ Verify `OCR_ENGINE=easyocr` (NOT tesseract)
2. ✅ Check language models loaded (should be EN only for speed)
3. ✅ Ensure `ENABLE_VISION_FALLBACK=false` by default
4. ✅ Clear corrupted model cache:
   ```bash
   docker compose exec backend rm -rf ~/.EasyOCR/model
   docker compose restart backend
   ```

---

### 2. ⏱️ High Latency (P95 >8s)

**Symptoms**: Slow OCR processing, timeouts

**Diagnosis**:
```bash
# Check metrics
curl -s http://localhost:8080/metrics | grep duration_seconds

# Monitor resource usage
docker stats backend
```

**Solutions**:
1. ✅ Enable image downscaling:
   ```bash
   # Add to .env
   MAX_IMAGE_SIZE=1920  # Limit long edge
   ENABLE_SUPERRES=false
   ```

2. ✅ Reduce OCR languages:
   ```python
   # backend/app/pipeline/ocr.py
   reader = easyocr.Reader(['en'], gpu=True)  # Not ['en','fr','de','es']
   ```

3. ✅ Check CPU throttling:
   ```bash
   # Increase CPU limits in docker-compose.yml
   deploy:
     resources:
       limits:
         cpus: '4'
         memory: 4G
   ```

---

### 3. 💾 Cache Not Working (0% hit rate)

**Symptoms**: Same image processed multiple times, no cache hits

**Diagnosis**:
```bash
# Check Redis connection
docker compose exec redis redis-cli ping

# Monitor cache operations
docker compose exec redis redis-cli MONITOR

# Check cache keys
docker compose exec redis redis-cli KEYS "ocr:*"
```

**Solutions**:
1. ✅ Verify Redis URL:
   ```bash
   # .env
   USE_REDIS=true
   REDIS_URL=redis://redis:6379/0  # Inside Docker
   # or
   REDIS_URL=redis://localhost:6379/0  # Outside Docker
   ```

2. ✅ Check cache key generation:
   ```python
   # Must include image hash + OCR params
   cache_key = f"ocr:{image_hash}:{ocr_config_hash}"
   ```

3. ✅ Verify TTL settings:
   ```bash
   # Should be >3600 seconds for OCR results
   docker compose exec redis redis-cli TTL "ocr:*"
   ```

---

### 4. 🔐 Authentication Errors

**Symptoms**: 401 Unauthorized on API calls

**Diagnosis**:
```bash
# Check JWT secret is set
docker compose exec backend env | grep JWT_SECRET

# Test export endpoints (should be public)
curl -X POST http://localhost:8080/api/export/mtga \
  -H "Content-Type: application/json" \
  -d '{"main":[{"qty":4,"name":"Island"}],"side":[]}'
```

**Solutions**:
1. ✅ Generate secure JWT secret:
   ```bash
   # Add to .env
   JWT_SECRET_KEY=$(openssl rand -base64 32)
   ```

2. ✅ Verify export endpoints are public:
   ```python
   # backend/app/core/auth_middleware.py
   if path.startswith("/api/export/"):
       return await call_next(request)  # Skip auth
   ```

---

### 5. 🐳 Docker Build Failures

**Symptoms**: Container won't start, build errors

**Diagnosis**:
```bash
# Check logs
docker compose logs backend

# Verify environment
docker compose config
```

**Solutions**:
1. ✅ For ARM64/M1/M2 Macs:
   ```dockerfile
   # Remove x86-specific packages
   # Not: libgthread-2.0-0 libquadmath0
   ```

2. ✅ Enable BuildKit:
   ```bash
   export DOCKER_BUILDKIT=1
   docker compose build --no-cache backend
   ```

3. ✅ Fix port conflicts:
   ```yaml
   # docker-compose.yml
   postgres:
     ports:
       - "5433:5432"  # External 5433, internal 5432
   ```

---

### 6. 📊 Missing Metrics

**Symptoms**: Prometheus metrics not appearing

**Diagnosis**:
```bash
# Check metrics endpoint
curl -s http://localhost:8080/metrics | grep -c screen2deck_
```

**Solutions**:
1. ✅ Enable metrics collection:
   ```python
   # backend/app/core/metrics.py
   from prometheus_client import Counter, Histogram, Gauge
   
   ocr_requests = Counter('s2d_ocr_requests_total', 'Total OCR requests')
   ocr_duration = Histogram('s2d_ocr_duration_seconds', 'OCR processing time')
   cache_hits = Counter('s2d_cache_hits_total', 'Cache hits')
   cache_misses = Counter('s2d_cache_misses_total', 'Cache misses')
   jobs_inflight = Gauge('s2d_jobs_inflight', 'Jobs currently processing')
   ```

2. ✅ Instrument code:
   ```python
   # In OCR processing
   with ocr_duration.time():
       result = process_ocr(image)
   ```

---

### 7. 🌐 CORS Errors

**Symptoms**: Browser blocks API requests

**Diagnosis**:
```bash
# Check CORS headers
curl -I -X OPTIONS http://localhost:8080/api/ocr/upload \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST"
```

**Solutions**:
1. ✅ Update allowed origins:
   ```bash
   # .env
   CORS_ORIGINS='["http://localhost:3000","http://localhost:3001"]'
   ```

2. ✅ Restart backend:
   ```bash
   docker compose restart backend
   ```

---

## Performance Tuning

### Quick Wins
1. **Reduce image size**: Downscale to 1920px max
2. **Load only English**: Remove other languages from EasyOCR
3. **Enable GPU**: Add `--gpus all` to docker run
4. **Increase workers**: Set `WEB_CONCURRENCY=4` in .env

### Monitoring Commands
```bash
# Real-time metrics
watch -n 1 'curl -s http://localhost:8080/metrics | grep s2d_'

# Cache stats
docker compose exec redis redis-cli INFO stats

# Container resources
docker stats --no-stream

# API latency test
ab -n 100 -c 10 http://localhost:8080/health
```

---

## Emergency Procedures

### 🔥 Complete Reset
```bash
# Stop everything
docker compose down -v

# Clean all data
rm -rf backend/app/data/*
rm -rf ~/.EasyOCR

# Rebuild from scratch
docker compose build --no-cache
docker compose up -d

# Download Scryfall data
docker compose exec backend python scripts/download_scryfall.py
```

### 📞 Escalation Path
1. Check this runbook first
2. Review logs: `docker compose logs --tail=100`
3. Run diagnostics: `./scripts/first_test.sh`
4. Check GitHub Issues for similar problems
5. Create new issue with:
   - Error messages
   - `docker compose ps` output
   - Environment details (OS, Docker version)
   - Steps to reproduce

---

## Useful Queries

### PromQL (Prometheus)
```promql
# P95 latency
histogram_quantile(0.95, 
  sum by (le) (
    rate(s2d_ocr_duration_seconds_bucket[5m])
  )
)

# Cache hit rate
rate(s2d_cache_hits_total[5m]) / 
(rate(s2d_cache_hits_total[5m]) + rate(s2d_cache_misses_total[5m]))

# Request rate
rate(s2d_ocr_requests_total[1m])
```

### Redis Commands
```redis
# Clear all cache
FLUSHDB

# Count OCR cache entries
KEYS ocr:* | wc -l

# Get cache TTL
TTL ocr:*

# Monitor operations
MONITOR
```

---

**Last Updated**: 2025-01-18
**Version**: 1.0.0
**Maintainer**: DevOps Team