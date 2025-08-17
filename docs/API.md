# Screen2Deck API Documentation v2.0

## 🌐 Base URL
```
Production: https://api.screen2deck.com
Development: http://localhost:8080
```

## 📚 API Documentation
- **OpenAPI/Swagger**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI Schema**: `/openapi.json`

## 🔐 Authentication

Screen2Deck uses JWT Bearer tokens and API keys for authentication.

### Register New User

```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "string",
  "email": "user@example.com",
  "password": "string"
}
```

**Response:**
```json
{
  "id": "user-123",
  "username": "string",
  "email": "user@example.com",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Login

```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

grant_type=password&username=demo&password=demo123
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Refresh Token

```http
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Generate API Key

```http
POST /api/auth/api-key
Content-Type: application/json
Authorization: Bearer <access_token>

{
  "name": "My API Key",
  "permissions": ["ocr:read", "ocr:write", "export:read"]
}
```

**Response:**
```json
{
  "key": "s2d_abc123...",
  "name": "My API Key",
  "created_at": "2024-01-01T00:00:00Z",
  "permissions": ["ocr:read", "ocr:write", "export:read"]
}
```

## 🏥 Health & Monitoring

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": 1704067200,
  "version": "2.0.0"
}
```

### Detailed Health

```http
GET /health/detailed
```

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "environment": "production",
  "system": {
    "cpu_percent": 25.5,
    "memory_percent": 45.2,
    "memory_used_gb": 3.6,
    "disk_percent": 60.0
  },
  "jobs": {
    "total": 1523,
    "queued": 5,
    "processing": 2,
    "completed": 1500,
    "failed": 16
  },
  "cache": {
    "total_cards": 15234,
    "active_cards": 14567,
    "total_hits": 45678,
    "db_size_mb": 125.4
  }
}
```

### Prometheus Metrics

```http
GET /metrics
```

Returns metrics in Prometheus format:
- `screen2deck_ocr_requests_total`
- `screen2deck_ocr_duration_seconds`
- `screen2deck_active_jobs`
- `screen2deck_cache_hits_total`
- `screen2deck_export_requests_total`
- `screen2deck_errors_total`

## 📸 OCR Endpoints

### Upload Image

```http
POST /api/ocr/upload
Content-Type: multipart/form-data
Authorization: Bearer <token> (optional for public endpoint)

file: <image_file>
```

**Features:**
- **Idempotency**: Same image returns cached result via SHA256 hash
- **Validation**: Comprehensive image validation and sanitization
- **Rate Limiting**: 10 requests/minute for unauthenticated, 30 for authenticated
- **Supported Formats**: JPEG, PNG, WebP, GIF, BMP, TIFF
- **Max Size**: 10MB
- **Max Dimensions**: 4096x4096 pixels

**Response:**
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "cached": false
}
```

### Get Job Status

```http
GET /api/ocr/status/{jobId}
Authorization: Bearer <token> (optional)
```

**Response:**
```json
{
  "state": "completed",
  "progress": 100,
  "result": {
    "jobId": "550e8400-e29b-41d4-a716-446655440000",
    "raw": {
      "spans": [
        {
          "text": "4 Lightning Bolt",
          "conf": 0.95
        }
      ],
      "mean_conf": 0.92
    },
    "parsed": {
      "main": [
        {
          "qty": 4,
          "name": "Lightning Bolt",
          "candidates": [
            {
              "name": "Lightning Bolt",
              "score": 1.0
            }
          ]
        }
      ],
      "side": []
    },
    "normalized": {
      "main": [
        {
          "qty": 4,
          "name": "Lightning Bolt",
          "scryfall_id": "a57af4df-566c-4c65-9cfe-31a96f8e4e3f"
        }
      ],
      "side": []
    },
    "timings_ms": {
      "total": 1250
    },
    "traceId": "trace-123"
  },
  "error": null
}
```

## 📤 Export Endpoints

### Export Deck

```http
POST /api/export/{format}
Content-Type: application/json
Authorization: Bearer <token>

{
  "main": [
    {
      "qty": 4,
      "name": "Lightning Bolt",
      "scryfall_id": "a57af4df-566c-4c65-9cfe-31a96f8e4e3f"
    }
  ],
  "side": []
}
```

**Supported Formats:**
- `mtga` - MTG Arena format
- `moxfield` - Moxfield format
- `archidekt` - Archidekt format
- `tappedout` - TappedOut format
- `json` - Raw JSON format

**Response:**
```json
{
  "text": "4 Lightning Bolt (2XM) 129\n...",
  "format": "mtga"
}
```

### List Export Formats

```http
GET /api/export/formats
```

**Response:**
```json
{
  "formats": [
    {
      "id": "mtga",
      "name": "MTG Arena",
      "description": "MTG Arena deck format",
      "example": "4 Lightning Bolt (2XM) 129"
    },
    {
      "id": "moxfield",
      "name": "Moxfield",
      "description": "Moxfield deck format",
      "example": "4 Lightning Bolt"
    }
  ]
}
```

## 🔒 Security Features

### Rate Limiting
- **Unauthenticated**: 10 requests/minute with burst of 3
- **Authenticated**: 30 requests/minute with burst of 10
- **Per-IP tracking** with memory-efficient cleanup

### Security Headers
All responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy: default-src 'self'...`

### Input Validation
- **Image Validation**: MIME type, dimensions, file size
- **Text Sanitization**: SQL injection and XSS prevention
- **Job ID Validation**: UUID format verification
- **Export Format Validation**: Whitelist of allowed formats

## 🚨 Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `BAD_IMAGE` | Invalid or corrupted image | 400 |
| `VALIDATION_ERROR` | Input validation failed | 400 |
| `UNAUTHORIZED` | Authentication required | 401 |
| `FORBIDDEN` | Insufficient permissions | 403 |
| `JOB_NOT_FOUND` | Job ID not found | 404 |
| `RATE_LIMIT` | Rate limit exceeded | 429 |
| `OCR_ERROR` | OCR processing failed | 500 |
| `EXPORT_INVALID` | Export format not supported | 400 |

## 📊 Response Headers

All responses include:
- `X-Request-ID`: Unique request identifier for tracing
- `X-Rate-Limit-Limit`: Rate limit maximum
- `X-Rate-Limit-Remaining`: Remaining requests
- `X-Rate-Limit-Reset`: Reset timestamp

## 🔄 WebSocket Support

Connect to WebSocket for real-time updates:

```javascript
const ws = new WebSocket('wss://api.screen2deck.com/ws');

ws.on('message', (data) => {
  const update = JSON.parse(data);
  console.log(`Job ${update.jobId}: ${update.progress}%`);
});
```

## 📝 Example Workflows

### Complete OCR Workflow

```bash
# 1. Login
TOKEN=$(curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=demo&password=demo123" \
  | jq -r '.access_token')

# 2. Upload image
JOB_ID=$(curl -X POST http://localhost:8080/api/ocr/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@deck.jpg" \
  | jq -r '.jobId')

# 3. Check status
curl http://localhost:8080/api/ocr/status/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"

# 4. Export to MTGA
curl -X POST http://localhost:8080/api/export/mtga \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"main":[{"qty":4,"name":"Lightning Bolt"}],"side":[]}'
```

### Using API Key

```bash
# Generate API key
API_KEY=$(curl -X POST http://localhost:8080/api/auth/api-key \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"CLI Tool"}' \
  | jq -r '.key')

# Use API key for requests
curl -X POST http://localhost:8080/api/ocr/upload \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@deck.jpg"
```

## 🧪 Testing

Test the API using the Swagger UI at `/docs` or with curl commands above.

For load testing:
```bash
cd backend
locust -f tests/load_test.py --host=http://localhost:8080
```

## 📖 SDK Support

Official SDKs coming soon:
- Python SDK
- JavaScript/TypeScript SDK
- Go SDK

## 🆘 Support

- GitHub Issues: https://github.com/gbordes77/Screen2Deck/issues
- API Status: https://status.screen2deck.com
- Documentation: https://docs.screen2deck.com