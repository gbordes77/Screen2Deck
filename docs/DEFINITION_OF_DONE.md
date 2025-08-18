# Definition of Done (DoD) - Screen2Deck

## ✅ Acceptance Criteria

For any feature or release to be considered "Done", it must meet ALL of the following criteria:

### 1. Functional Requirements

#### OCR Performance
- [ ] **Accuracy**: ≥95% exact match on `validation_set/` test images
- [ ] **Fuzzy Accuracy**: ≥60% with 85% similarity threshold  
- [ ] **Processing Time**: P95 ≤ 5s on production hardware (≤8s on CI)
- [ ] **Success Rate**: ≥98% of valid images processed successfully

#### Cache Performance
- [ ] **Hit Rate**: ≥50% on second benchmark pass
- [ ] **Redis Integration**: Cache metrics exposed and functional
- [ ] **Idempotency**: Same image returns same jobId when re-uploaded

#### Export Formats
- [ ] **MTGA Format**: 100% compliant with Arena import
- [ ] **Moxfield Format**: Valid JSON structure with all fields
- [ ] **Archidekt Format**: Proper CSV formatting
- [ ] **TappedOut Format**: Correct text format with categories

### 2. Quality Gates

#### Code Quality
- [ ] **Tests Pass**: All unit, integration, and E2E tests green
- [ ] **Coverage**: ≥80% for critical paths (OCR, matching, export)
- [ ] **Linting**: No critical issues from ruff/ESLint
- [ ] **Type Safety**: TypeScript/Python type hints complete

#### Security
- [ ] **No Hardcoded Secrets**: All secrets in environment variables
- [ ] **CORS Configured**: Restrictive origin list
- [ ] **Input Validation**: All uploads validated (magic numbers, size)
- [ ] **Rate Limiting**: Enabled on public endpoints

#### Documentation
- [ ] **API Documentation**: OpenAPI spec up-to-date
- [ ] **README**: Installation and usage instructions current
- [ ] **Inline Comments**: Complex logic documented
- [ ] **Runbook**: Troubleshooting guide available

### 3. CI/CD Requirements

#### Automated Checks
- [ ] **Independent Benchmark**: CI workflow passes with thresholds met
- [ ] **Build Success**: Docker images build without errors
- [ ] **Health Checks**: All services report healthy status
- [ ] **Artifact Generation**: Benchmark reports uploaded to GitHub

#### Deployment Readiness
- [ ] **Environment Variables**: All required vars documented
- [ ] **Database Migrations**: Applied successfully
- [ ] **Scryfall Data**: Bulk data downloaded and cached
- [ ] **Model Downloads**: EasyOCR models cached in image

### 4. Monitoring & Observability

#### Metrics
- [ ] **Prometheus Metrics**: Core metrics exposed
  - `s2d_ocr_request_duration_seconds` (histogram)
  - `s2d_cache_hits_total` / `s2d_cache_misses_total`
  - `s2d_jobs_inflight` (gauge)
- [ ] **Health Endpoint**: Returns detailed component status
- [ ] **Structured Logging**: TraceID present in all logs

### 5. User Experience

#### Frontend
- [ ] **Loading States**: Clear feedback during processing
- [ ] **Error Handling**: User-friendly error messages
- [ ] **Responsive Design**: Works on mobile and desktop
- [ ] **Accessibility**: Basic WCAG compliance (labels, keyboard nav)

#### Performance
- [ ] **Initial Load**: <3s on 3G network
- [ ] **Progressive Enhancement**: Core features work without JS
- [ ] **Optimized Assets**: Images and bundles compressed

## 📋 Release Checklist

Before any release to production:

1. **Run Independent Benchmark**
   ```bash
   make bench-truth
   # Verify accuracy ≥95%, P95 ≤5s
   ```

2. **Validate Exports**
   ```bash
   make golden
   # All 4 formats must pass
   ```

3. **Security Scan**
   ```bash
   # Check for secrets
   git secrets --scan
   # Run security audit
   npm audit
   pip-audit
   ```

4. **Load Test**
   ```bash
   # Run Locust with 100 users
   locust -f tests/load/locustfile.py --users 100
   ```

5. **First Test Script**
   ```bash
   ./scripts/first_test.sh
   # All 8 steps must pass
   ```

## 🚨 Blocking Issues

The following issues MUST be resolved before marking as Done:

1. **Accuracy <40%**: System is fundamentally broken
2. **P95 >10s**: Unacceptable user experience
3. **Hardcoded Secrets**: Security vulnerability
4. **No Cache**: Redis must be functional
5. **Export Failures**: All 4 formats must work
6. **CI Red**: All GitHub Actions must pass

## 📊 Metrics Tracking

Track these metrics over time:

| Metric | Target | Current | Trend |
|--------|--------|---------|-------|
| Exact Accuracy | ≥95% | TBD | - |
| P95 Latency | ≤5s | TBD | - |
| Cache Hit Rate | ≥50% | TBD | - |
| CI Pass Rate | 100% | TBD | - |
| Test Coverage | ≥80% | TBD | - |

## 🔄 Continuous Improvement

After each release, review:

1. **Metrics**: Did we meet all thresholds?
2. **Incidents**: What broke and why?
3. **Feedback**: User complaints or suggestions
4. **Tech Debt**: What needs refactoring?
5. **Performance**: Optimization opportunities

---

**Last Updated**: 2025-01-18
**Version**: 1.0.0
**Owner**: Engineering Team