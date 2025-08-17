# Screen2Deck API Documentation

## Base URL
```
Production: https://api.screen2deck.com
Development: http://localhost:8080
```

## Authentication

Screen2Deck uses JWT Bearer tokens for authentication. Some endpoints also support API keys.

### Get Access Token

```http
POST /api/auth/token
Content-Type: application/json

{
  "username": "string",
  "password": "string"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Refresh Token

```http
POST /api/auth/refresh
Content-Type: application/json
Authorization: Bearer <refresh_token>
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Using Authentication

Include the token in the Authorization header:
```http
Authorization: Bearer <access_token>
```

Or use an API key:
```http
X-API-Key: s2d_your_api_key_here
```

## Core Endpoints

### Upload Image for OCR

```http
POST /api/ocr/upload
Content-Type: multipart/form-data

file: <image_file>
```

**Parameters:**
- `file` (required): Image file (JPEG, PNG, WebP)
- Maximum file size: 10MB

**Response:**
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Image uploaded successfully",
  "estimatedTime": 2
}
```

**Status Codes:**
- `200 OK`: Upload successful
- `400 Bad Request`: Invalid file format
- `413 Payload Too Large`: File exceeds size limit
- `429 Too Many Requests`: Rate limit exceeded

### Get OCR Status

```http
GET /api/ocr/status/{job_id}
```

**Parameters:**
- `job_id` (required): Job UUID from upload response

**Response:**
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "state": "completed",
  "progress": 100,
  "result": {
    "raw": [
      {"qty": 4, "name": "Lightning Bolt", "confidence": 0.95},
      {"qty": 4, "name": "Counterspell", "confidence": 0.92}
    ],
    "normalized": {
      "main": [
        {
          "qty": 4,
          "name": "Lightning Bolt",
          "scryfall_id": "a57af4df-566c-4c65-9cfe-31a96f8e4e3f",
          "set": "2xm",
          "collector_number": "129"
        }
      ],
      "side": []
    },
    "errors": [],
    "warnings": ["Card 'Unknown Card' not found in database"]
  },
  "createdAt": "2024-01-20T10:30:00Z",
  "completedAt": "2024-01-20T10:30:02Z"
}
```

**States:**
- `pending`: Job queued
- `processing`: OCR in progress
- `validating`: Validating cards against Scryfall
- `completed`: Successfully processed
- `failed`: Processing failed

### Export Deck

```http
POST /api/export/{format}
Content-Type: application/json

{
  "main": [
    {"qty": 4, "name": "Lightning Bolt", "scryfall_id": "..."}
  ],
  "side": [
    {"qty": 2, "name": "Pyroblast", "scryfall_id": "..."}
  ]
}
```

**Formats:**
- `mtga`: Magic: The Gathering Arena
- `moxfield`: Moxfield
- `archidekt`: Archidekt
- `tappedout`: TappedOut
- `json`: Raw JSON format

**Response (MTGA example):**
```
Deck
4 Lightning Bolt (2XM) 129
4 Counterspell (MH2) 267

Sideboard
2 Pyroblast (ICE) 213
```

### Validate Cards

```http
POST /api/cards/validate
Content-Type: application/json

{
  "cards": [
    "Lightning Bolt",
    "Counterspell",
    "Invalid Card Name"
  ]
}
```

**Response:**
```json
{
  "valid": [
    {
      "name": "Lightning Bolt",
      "scryfall_id": "a57af4df-566c-4c65-9cfe-31a96f8e4e3f",
      "oracle_text": "Lightning Bolt deals 3 damage to any target.",
      "mana_cost": "{R}",
      "type_line": "Instant"
    }
  ],
  "invalid": ["Invalid Card Name"],
  "suggestions": {
    "Invalid Card Name": ["Valid Card Name", "Another Valid Card"]
  }
}
```

### Search Cards

```http
GET /api/cards/search?q={query}&limit={limit}
```

**Parameters:**
- `q` (required): Search query
- `limit` (optional): Maximum results (default: 10, max: 100)
- `fuzzy` (optional): Enable fuzzy matching (default: true)

**Response:**
```json
{
  "results": [
    {
      "name": "Lightning Bolt",
      "scryfall_id": "a57af4df-566c-4c65-9cfe-31a96f8e4e3f",
      "image_uri": "https://cards.scryfall.io/...",
      "prices": {
        "usd": "1.50",
        "eur": "1.20"
      }
    }
  ],
  "total": 15,
  "has_more": true
}
```

## WebSocket API

### Connect to Job Updates

```javascript
const ws = new WebSocket('ws://localhost:8080/ws/{job_id}?token={jwt_token}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Status:', data.state);
  console.log('Progress:', data.progress);
};

// Send commands
ws.send('ping');  // Keepalive
ws.send('status'); // Request current status
```

**Message Format:**
```json
{
  "type": "update",
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "state": "processing",
  "progress": 45,
  "message": "Analyzing image..."
}
```

**Message Types:**
- `update`: Status update
- `progress`: Progress percentage
- `complete`: Job completed
- `error`: Error occurred
- `pong`: Response to ping

## Health & Monitoring

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "database": "connected",
    "redis": "connected",
    "celery": "running"
  },
  "uptime": 3600
}
```

### Metrics (Prometheus Format)

```http
GET /metrics
```

**Response:**
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/api/ocr/status",status="200"} 1234

# HELP ocr_processing_duration_seconds OCR processing duration
# TYPE ocr_processing_duration_seconds histogram
ocr_processing_duration_seconds_bucket{le="1.0"} 456
ocr_processing_duration_seconds_bucket{le="2.0"} 789
```

## Rate Limiting

Default rate limits:
- **Anonymous**: 10 requests/minute
- **Authenticated**: 30 requests/minute
- **API Key**: 100 requests/minute

Rate limit headers:
```http
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1642684800
```

## Error Responses

### Standard Error Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input provided",
    "details": {
      "field": "file",
      "reason": "File type not supported"
    }
  },
  "timestamp": "2024-01-20T10:30:00Z",
  "path": "/api/ocr/upload",
  "request_id": "req_123456"
}
```

### Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `VALIDATION_ERROR` | Invalid input | 400 |
| `AUTHENTICATION_ERROR` | Invalid credentials | 401 |
| `PERMISSION_DENIED` | Insufficient permissions | 403 |
| `NOT_FOUND` | Resource not found | 404 |
| `RATE_LIMIT_EXCEEDED` | Too many requests | 429 |
| `INTERNAL_ERROR` | Server error | 500 |
| `SERVICE_UNAVAILABLE` | Service down | 503 |

## SDK Examples

### Python

```python
import requests
from typing import Dict, List

class Screen2DeckClient:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def authenticate(self, username: str, password: str):
        response = self.session.post(
            f"{self.base_url}/api/auth/token",
            json={"username": username, "password": password}
        )
        token = response.json()["access_token"]
        self.session.headers["Authorization"] = f"Bearer {token}"
    
    def upload_image(self, image_path: str) -> str:
        with open(image_path, 'rb') as f:
            response = self.session.post(
                f"{self.base_url}/api/ocr/upload",
                files={'file': f}
            )
        return response.json()["jobId"]
    
    def get_status(self, job_id: str) -> Dict:
        response = self.session.get(
            f"{self.base_url}/api/ocr/status/{job_id}"
        )
        return response.json()
    
    def export_deck(self, deck_data: Dict, format: str = "mtga") -> str:
        response = self.session.post(
            f"{self.base_url}/api/export/{format}",
            json=deck_data
        )
        return response.text

# Usage
client = Screen2DeckClient()
client.authenticate("user", "pass")
job_id = client.upload_image("deck.jpg")
status = client.get_status(job_id)
if status["state"] == "completed":
    deck_list = client.export_deck(status["result"]["normalized"])
    print(deck_list)
```

### JavaScript/TypeScript

```typescript
interface DeckCard {
  qty: number;
  name: string;
  scryfall_id?: string;
}

interface DeckData {
  main: DeckCard[];
  side: DeckCard[];
}

class Screen2DeckClient {
  private baseUrl: string;
  private token?: string;

  constructor(baseUrl: string = 'http://localhost:8080') {
    this.baseUrl = baseUrl;
  }

  async authenticate(username: string, password: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await response.json();
    this.token = data.access_token;
  }

  async uploadImage(file: File): Promise<string> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${this.baseUrl}/api/ocr/upload`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`
      },
      body: formData
    });
    
    const data = await response.json();
    return data.jobId;
  }

  async getStatus(jobId: string): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}/api/ocr/status/${jobId}`,
      {
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      }
    );
    return response.json();
  }

  async exportDeck(deckData: DeckData, format: string = 'mtga'): Promise<string> {
    const response = await fetch(
      `${this.baseUrl}/api/export/${format}`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(deckData)
      }
    );
    return response.text();
  }
}

// Usage
const client = new Screen2DeckClient();
await client.authenticate('user', 'pass');
const jobId = await client.uploadImage(fileInput.files[0]);
const status = await client.getStatus(jobId);
if (status.state === 'completed') {
  const deckList = await client.exportDeck(status.result.normalized);
  console.log(deckList);
}
```

## Postman Collection

Import this collection to test the API:

```json
{
  "info": {
    "name": "Screen2Deck API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Authentication",
      "item": [
        {
          "name": "Get Token",
          "request": {
            "method": "POST",
            "header": [],
            "body": {
              "mode": "raw",
              "raw": "{\"username\": \"test\", \"password\": \"test\"}",
              "options": {
                "raw": {
                  "language": "json"
                }
              }
            },
            "url": {
              "raw": "{{base_url}}/api/auth/token",
              "host": ["{{base_url}}"],
              "path": ["api", "auth", "token"]
            }
          }
        }
      ]
    },
    {
      "name": "OCR",
      "item": [
        {
          "name": "Upload Image",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Authorization",
                "value": "Bearer {{token}}"
              }
            ],
            "body": {
              "mode": "formdata",
              "formdata": [
                {
                  "key": "file",
                  "type": "file",
                  "src": "/path/to/deck.jpg"
                }
              ]
            },
            "url": {
              "raw": "{{base_url}}/api/ocr/upload",
              "host": ["{{base_url}}"],
              "path": ["api", "ocr", "upload"]
            }
          }
        }
      ]
    }
  ],
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8080"
    },
    {
      "key": "token",
      "value": ""
    }
  ]
}
```

## OpenAPI Specification

Access the interactive API documentation:
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc
- OpenAPI JSON: http://localhost:8080/openapi.json