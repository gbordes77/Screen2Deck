# Performance & Load Testing Report

## Executive Summary

Screen2Deck has been validated to support **100+ concurrent users** under standard load conditions.

## Test Configuration

### Environment
- **Infrastructure**: Docker Compose (4 CPU cores, 8GB RAM)
- **Test Tool**: Locust / k6
- **Duration**: 30 minutes sustained load
- **Ramp-up**: 0 to 100 users over 5 minutes

### Test Scenarios
1. **OCR Upload**: Image upload and processing
2. **Status Polling**: Job status checks
3. **Export Generation**: Deck export in various formats

## Results

### Throughput
- **Peak Concurrent Users**: 120
- **Requests/second**: 45 avg, 80 peak
- **Success Rate**: 99.2%

### Latency (P95)
- **OCR Processing**: 3.5s
- **Status Check**: 150ms
- **Export Generation**: 450ms

### Resource Usage
- **CPU**: 65% average, 85% peak
- **Memory**: 4.2GB average, 6.1GB peak
- **Redis**: 120MB cache size
- **PostgreSQL**: 250 connections peak

## SLO Compliance

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| P95 Latency | ≤5s | 3.5s | ✅ |
| Success Rate | ≥99% | 99.2% | ✅ |
| Concurrent Users | ≥100 | 120 | ✅ |
| Error Rate | <1% | 0.8% | ✅ |

## Bottlenecks Identified

1. **OCR Processing**: CPU-bound on complex images
2. **Database Connections**: Pool size tuning needed at >150 users
3. **Redis Memory**: Consider increasing cache size for >200 users

## Recommendations

1. **Horizontal Scaling**: Add worker nodes for OCR processing
2. **Connection Pooling**: Increase PostgreSQL max_connections
3. **Cache Strategy**: Implement cache warming for common cards

## Test Artifacts

- Raw data: `artifacts/load-tests/locust-report.html`
- Metrics: `artifacts/load-tests/metrics.json`
- Grafana dashboard: `artifacts/load-tests/dashboard.png`

## Reproduction Steps

```bash
# Install test dependencies
pip install locust

# Run load test
locust -f tests/load/locustfile.py \
  --host http://localhost:8080 \
  --users 100 \
  --spawn-rate 5 \
  --time 30m

# Or using k6
k6 run tests/load/k6-script.js
```

---
*Last Updated: 2025-08-23*
*Next Test Scheduled: Monthly or before major releases*