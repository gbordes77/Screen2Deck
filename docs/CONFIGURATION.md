# ⚙️ Screen2Deck Configuration Guide

This guide covers all configuration options for Screen2Deck, from development to production deployment.

## Environment Variables

### Core Application Settings

```env
# Application Environment
APP_ENV=production              # development | staging | production
PORT=8080                      # API server port
LOG_LEVEL=INFO                 # DEBUG | INFO | WARNING | ERROR
DEBUG=false                    # Enable debug mode
```

### Security Configuration

```env
# JWT Authentication (REQUIRED - MUST CHANGE!)
JWT_SECRET_KEY=your-secure-32-char-minimum-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
API_KEY_PREFIX=s2d_

# CORS Settings
CORS_ORIGINS=["https://screen2deck.com","https://www.screen2deck.com"]
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=["GET","POST"]
CORS_ALLOW_HEADERS=["*"]
```

### Database Configuration

```env
# PostgreSQL (Optional - for user management)
DATABASE_URL=postgresql://screen2deck:password@postgres:5432/screen2deck
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Redis (Required for job storage)
USE_REDIS=true
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your-redis-password  # Optional but recommended
REDIS_POOL_SIZE=10
```

### OCR Configuration

```env
# OCR Processing
ENABLE_VISION_FALLBACK=false      # Enable OpenAI Vision fallback
ENABLE_SUPERRES=false              # Enable super-resolution preprocessing
OCR_MIN_CONF=0.62                  # Minimum confidence threshold
OCR_MIN_LINES=10                   # Minimum lines for valid result
MAX_IMAGE_MB=10                    # Maximum upload size in MB
FUZZY_MATCH_TOPK=5                 # Number of fuzzy match candidates
```

### Scryfall Integration

```env
# Scryfall API
ALWAYS_VERIFY_SCRYFALL=true
ENABLE_SCRYFALL_ONLINE_FALLBACK=true
SCRYFALL_API_TIMEOUT=5
SCRYFALL_API_RATE_LIMIT_MS=120
SCRYFALL_DB=./app/data/scryfall_cache.sqlite
SCRYFALL_BULK_PATH=./app/data/scryfall-default-cards.json
```

### OpenAI Configuration (Optional)

```env
# OpenAI Vision API (for fallback OCR)
OPENAI_API_KEY=sk-your-openai-api-key-here
```

### Monitoring Configuration

```env
# Metrics & Tracing
ENABLE_METRICS=true
METRICS_PORT=9090
ENABLE_TRACING=false
JAEGER_AGENT_HOST=localhost
JAEGER_AGENT_PORT=6831
```

### Rate Limiting

```env
# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=30
RATE_LIMIT_PER_HOUR=1000
```

### Feature Flags

```env
# Feature Toggles
FEATURE_WEBSOCKET=true
FEATURE_GRAPHQL=false
FEATURE_ASYNC_PROCESSING=true
```

## Configuration Files

### Docker Environment (.env.docker)

```env
# Docker-specific configuration
DOCKER_REGISTRY=docker.io
IMAGE_TAG=latest
COMPOSE_PROJECT_NAME=screen2deck
DOCKER_BUILDKIT=1
```

### Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: screen2deck-config
  namespace: screen2deck
data:
  APP_ENV: "production"
  PORT: "8080"
  LOG_LEVEL: "INFO"
  ENABLE_METRICS: "true"
  CORS_ORIGINS: '["https://screen2deck.com"]'
  REDIS_URL: "redis://redis-service:6379/0"
```

### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: screen2deck-secrets
  namespace: screen2deck
type: Opaque
stringData:
  JWT_SECRET_KEY: "your-super-secret-jwt-key-minimum-32-chars"
  DATABASE_URL: "postgresql://user:pass@postgres:5432/screen2deck"
  REDIS_PASSWORD: "your-redis-password"
  OPENAI_API_KEY: "sk-your-openai-api-key"
```

## Production Configuration Checklist

### Security Settings

- [ ] Generate secure JWT_SECRET_KEY (32+ characters)
- [ ] Set strong database passwords
- [ ] Configure Redis authentication
- [ ] Update CORS_ORIGINS for your domain
- [ ] Enable HTTPS/TLS only
- [ ] Set APP_ENV=production
- [ ] Disable DEBUG mode

### Performance Settings

- [ ] Optimize DATABASE_POOL_SIZE for load
- [ ] Configure REDIS_POOL_SIZE
- [ ] Set appropriate rate limits
- [ ] Enable caching mechanisms
- [ ] Configure CDN if applicable

### Monitoring Settings

- [ ] Enable Prometheus metrics
- [ ] Configure Jaeger tracing (optional)
- [ ] Set appropriate LOG_LEVEL
- [ ] Configure alerting thresholds

## Configuration by Environment

### Development

```env
APP_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG
JWT_SECRET_KEY=dev-secret-key-for-local-testing-only
DATABASE_URL=postgresql://dev:dev@localhost:5432/screen2deck_dev
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=["http://localhost:3000","http://localhost:3001"]
RATE_LIMIT_ENABLED=false
```

### Staging

```env
APP_ENV=staging
DEBUG=false
LOG_LEVEL=INFO
JWT_SECRET_KEY=${STAGING_JWT_SECRET}
DATABASE_URL=${STAGING_DATABASE_URL}
REDIS_URL=${STAGING_REDIS_URL}
CORS_ORIGINS=["https://staging.screen2deck.com"]
RATE_LIMIT_ENABLED=true
ENABLE_METRICS=true
```

### Production

```env
APP_ENV=production
DEBUG=false
LOG_LEVEL=WARNING
JWT_SECRET_KEY=${PROD_JWT_SECRET}
DATABASE_URL=${PROD_DATABASE_URL}
REDIS_URL=${PROD_REDIS_URL}
REDIS_PASSWORD=${PROD_REDIS_PASSWORD}
CORS_ORIGINS=["https://screen2deck.com","https://www.screen2deck.com"]
RATE_LIMIT_ENABLED=true
ENABLE_METRICS=true
ENABLE_TRACING=true
```

## Advanced Configuration

### Custom Rate Limiting

```python
# app/core/config.py
RATE_LIMIT_RULES = {
    "/api/ocr/upload": {
        "unauthenticated": {"requests_per_minute": 10, "burst": 3},
        "authenticated": {"requests_per_minute": 30, "burst": 10}
    },
    "/api/export/*": {
        "authenticated": {"requests_per_minute": 20, "burst": 5}
    }
}
```

### Custom Security Headers

```python
# app/core/config.py
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'..."
}
```

### Database Connection Tuning

```python
# PostgreSQL connection pool settings
DATABASE_CONFIG = {
    "pool_size": 20,           # Number of persistent connections
    "max_overflow": 40,        # Maximum overflow connections
    "pool_timeout": 30,        # Timeout for getting connection
    "pool_recycle": 3600,      # Recycle connections after 1 hour
    "pool_pre_ping": True,     # Test connections before use
    "echo": False,             # Log SQL statements (debug only)
}
```

### Redis Configuration

```python
# Redis connection settings
REDIS_CONFIG = {
    "decode_responses": True,
    "max_connections": 50,
    "socket_keepalive": True,
    "socket_keepalive_options": {
        1: 1,  # TCP_KEEPIDLE
        2: 1,  # TCP_KEEPINTVL
        3: 3,  # TCP_KEEPCNT
    },
    "retry_on_timeout": True,
    "health_check_interval": 30,
}
```

## Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name api.screen2deck.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/api.screen2deck.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.screen2deck.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
    
    # Proxy Settings
    location /api {
        proxy_pass http://backend:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
}
```

## Troubleshooting Configuration

### Common Issues

#### JWT Secret Error
```
Error: JWT_SECRET_KEY must be at least 32 characters
Solution: Generate a secure key:
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### Redis Connection Failed
```
Error: Cannot connect to Redis
Solution: Check REDIS_URL and ensure Redis is running:
redis-cli ping
```

#### CORS Error
```
Error: CORS policy blocked request
Solution: Add your domain to CORS_ORIGINS:
CORS_ORIGINS=["https://yourdomain.com"]
```

#### Database Connection Pool Exhausted
```
Error: TimeoutError: QueuePool limit exceeded
Solution: Increase DATABASE_POOL_SIZE and DATABASE_MAX_OVERFLOW
```

### Configuration Validation

```bash
# Validate configuration
python -c "from app.core.config import settings; print(settings.dict())"

# Test database connection
python -c "from app.db.database import test_connection; test_connection()"

# Test Redis connection
redis-cli -u $REDIS_URL ping

# Check environment variables
env | grep -E "^(APP_|JWT_|DATABASE_|REDIS_)"
```

## Configuration Management Best Practices

1. **Never commit secrets** to version control
2. **Use environment variables** for sensitive data
3. **Rotate secrets regularly** (quarterly minimum)
4. **Use different secrets** per environment
5. **Monitor configuration changes** in audit logs
6. **Document all settings** and their purposes
7. **Validate configuration** on startup
8. **Use secure defaults** when possible
9. **Implement configuration versioning**
10. **Test configuration changes** in staging first

---

**Last Updated**: August 2024
**Configuration Support**: config@screen2deck.com