# 🔒 Screen2Deck Security Documentation

## Overview

Screen2Deck implements enterprise-grade security measures to protect user data and ensure system integrity. This document details our security architecture, features, and best practices.

## Security Architecture

### Defense in Depth

We implement multiple layers of security:

```
┌─────────────────────────────────────────────┐
│            External Firewall                 │
├─────────────────────────────────────────────┤
│          Load Balancer (HTTPS)               │
├─────────────────────────────────────────────┤
│         Security Headers Middleware          │
├─────────────────────────────────────────────┤
│        Authentication Middleware             │
├─────────────────────────────────────────────┤
│          Rate Limiting Layer                 │
├─────────────────────────────────────────────┤
│         Input Validation Layer               │
├─────────────────────────────────────────────┤
│           Application Logic                  │
├─────────────────────────────────────────────┤
│         Database Access Layer                │
└─────────────────────────────────────────────┘
```

## Authentication & Authorization

### JWT-Based Authentication

```python
# Token Structure
{
  "sub": "username",
  "user_id": "user-123",
  "permissions": ["ocr:read", "ocr:write", "export:read"],
  "exp": 1704067200,
  "iat": 1704063600
}
```

**Features:**
- **HS256 Algorithm**: Secure token signing
- **30-minute Access Tokens**: Short-lived for security
- **7-day Refresh Tokens**: Balance between security and UX
- **Secure Secret Generation**: Automatic secure key generation

### API Key Authentication

```python
# API Key Format
s2d_<32-character-random-string>
```

**Features:**
- **Prefixed Keys**: Easy identification and revocation
- **SHA256 Storage**: Keys stored as hashes
- **Permission Scopes**: Fine-grained access control
- **Audit Trail**: Usage tracking and logging

### Password Security

- **Bcrypt Hashing**: Industry-standard password hashing
- **Salt Rounds**: 12 rounds for optimal security/performance
- **Password Requirements**: Minimum 8 characters (configurable)

## Input Validation & Sanitization

### Image Validation

```python
# Validation Pipeline
1. File Extension Check     → .jpg, .png, .webp, etc.
2. MIME Type Verification   → Using python-magic
3. File Size Limits        → Max 10MB
4. Dimension Constraints   → Max 4096x4096
5. Content Sanitization    → Re-encode to remove metadata
```

### Text Input Sanitization

```python
# Sanitization Steps
1. Remove Control Characters
2. Normalize Whitespace  
3. Length Limiting
4. SQL Injection Prevention
5. XSS Protection
```

### Request Validation

- **UUID Format**: Job ID validation
- **Enum Values**: Export format whitelist
- **Pagination Limits**: Max 100 items per page
- **Header Validation**: Block suspicious headers

## Rate Limiting

### Configuration

| Endpoint | Unauthenticated | Authenticated | Burst |
|----------|----------------|---------------|-------|
| `/api/ocr/upload` | 10/min | 30/min | 3 |
| `/api/ocr/status` | 60/min | 100/min | 10 |
| `/api/export/*` | N/A | 30/min | 5 |

### Implementation

```python
# Memory-efficient rate limiting
- Per-IP tracking
- Sliding window algorithm
- Automatic cleanup (>1000 IPs)
- Redis backend for distributed systems
```

## Security Headers

### Default Headers

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'...
```

### CORS Configuration

```python
CORS_ORIGINS = [
    "http://localhost:3000",  # Development
    "https://screen2deck.com" # Production
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "POST"]
```

## Data Protection

### Encryption

- **TLS 1.2+**: All traffic encrypted in transit
- **Database Encryption**: At-rest encryption (PostgreSQL)
- **Redis Encryption**: TLS support for Redis connections

### Data Privacy

- **No PII Storage**: Minimal user data collection
- **Image Processing**: Images processed in memory, not stored
- **Job Expiration**: Automatic cleanup after 24 hours
- **GDPR Compliance**: Right to deletion, data export

### Idempotency

```python
# Image Hash-Based Deduplication
SHA256(image) → Check cache → Return existing or process new
```

Benefits:
- Prevents duplicate processing
- Reduces server load
- Improves user experience
- Enables caching

## Container Security

### Docker Best Practices

```dockerfile
# Non-root user
USER app:app

# Read-only filesystem
RUN chmod -R 555 /app

# No privileged operations
CAPABILITY DROP ALL

# Security scanning
RUN trivy scan .
```

### Kubernetes Security

```yaml
# Pod Security Policy
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: true
```

## Vulnerability Management

### Dependency Scanning

```bash
# Python dependencies
pip-audit requirements.txt

# Node.js dependencies
npm audit

# Docker images
trivy image screen2deck:latest
```

### Security Updates

- **Automated Dependabot**: GitHub security updates
- **Weekly Scans**: Scheduled vulnerability scanning
- **CVE Monitoring**: Track known vulnerabilities
- **Patch Timeline**: Critical within 24h, High within 7d

## Incident Response

### Security Incidents

1. **Detection**: Monitoring and alerting
2. **Containment**: Isolate affected systems
3. **Investigation**: Root cause analysis
4. **Remediation**: Fix vulnerabilities
5. **Recovery**: Restore normal operations
6. **Post-Mortem**: Document lessons learned

### Contact

Security issues should be reported to:
- Email: security@screen2deck.com
- GitHub Security Advisories: Private vulnerability reporting

## Compliance

### Standards

- **OWASP Top 10**: Protection against common vulnerabilities
- **CWE/SANS Top 25**: Secure coding practices
- **GDPR**: Data protection compliance
- **SOC 2 Type II**: (Planned) Security controls

### Audit Trail

```python
# Logged Events
- Authentication attempts
- API key usage
- Rate limit violations
- Security header violations
- Input validation failures
- Error conditions
```

## Security Checklist

### Pre-Deployment

- [ ] Change default JWT secret
- [ ] Configure strong database passwords
- [ ] Enable Redis authentication
- [ ] Update CORS origins
- [ ] Configure HTTPS/TLS
- [ ] Review rate limits
- [ ] Enable monitoring
- [ ] Set up alerting
- [ ] Run security scan
- [ ] Review access logs

### Post-Deployment

- [ ] Monitor security alerts
- [ ] Review access patterns
- [ ] Update dependencies
- [ ] Rotate secrets quarterly
- [ ] Conduct security audits
- [ ] Update documentation
- [ ] Train team on security
- [ ] Test incident response
- [ ] Review compliance
- [ ] Update security headers

## Best Practices for Users

### API Key Management

```bash
# Store keys securely
export S2D_API_KEY=$(cat ~/.screen2deck/api_key)

# Never commit keys
echo "S2D_API_KEY" >> .gitignore

# Rotate regularly
curl -X POST /api/auth/rotate-key
```

### Secure Integration

```python
# Use environment variables
api_key = os.environ.get("S2D_API_KEY")

# Validate SSL certificates
requests.get(url, verify=True)

# Handle errors gracefully
try:
    response = api_call()
except AuthenticationError:
    refresh_token()
```

## Security Tools

### Recommended Tools

- **OWASP ZAP**: Web application security testing
- **Burp Suite**: Security testing platform
- **SQLMap**: SQL injection testing
- **Metasploit**: Penetration testing
- **Wireshark**: Network protocol analysis

### Testing Commands

```bash
# Test rate limiting
for i in {1..20}; do curl http://localhost:8080/api/ocr/upload; done

# Test authentication
curl -H "Authorization: Bearer invalid" http://localhost:8080/api/ocr/status/123

# Test input validation
curl -X POST http://localhost:8080/api/ocr/upload \
  -F "file=@malicious.exe"
```

## Responsible Disclosure

We appreciate security researchers who help us maintain the security of Screen2Deck. If you discover a vulnerability:

1. **Do NOT** disclose publicly
2. Email security@screen2deck.com with details
3. Allow 90 days for patch development
4. Coordinate disclosure timeline

### Recognition

Security researchers who report valid vulnerabilities will be:
- Acknowledged in our security hall of fame
- Eligible for bug bounty rewards (coming soon)
- Provided with reference letters upon request

---

**Last Updated**: August 2024
**Security Contact**: security@screen2deck.com