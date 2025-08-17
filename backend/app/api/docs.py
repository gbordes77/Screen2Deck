"""
OpenAPI/Swagger documentation configuration.
Provides comprehensive API documentation with examples.
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from typing import Dict, Any

def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """Generate custom OpenAPI schema with examples."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Screen2Deck API",
        version="1.0.0",
        description="""
        ## 🎯 Screen2Deck OCR API
        
        AI-powered Magic: The Gathering deck scanner that converts card images to digital formats.
        
        ### Features
        - 🖼️ **OCR Processing**: Advanced image recognition with EasyOCR
        - 🔍 **Card Validation**: Automatic Scryfall verification
        - 📤 **Multi-Format Export**: MTGA, Moxfield, Archidekt, TappedOut
        - ⚡ **GPU Acceleration**: 3-5x faster processing with CUDA
        - 🔒 **JWT Authentication**: Secure API access
        - 📊 **Real-time Updates**: WebSocket support for job status
        
        ### Authentication
        This API uses JWT Bearer tokens. Include the token in the Authorization header:
        ```
        Authorization: Bearer <your-token>
        ```
        
        ### Rate Limiting
        - 30 requests per minute per IP
        - 1000 requests per hour per IP
        """,
        routes=app.routes,
        tags=[
            {
                "name": "OCR",
                "description": "OCR processing operations"
            },
            {
                "name": "Export",
                "description": "Deck export operations"
            },
            {
                "name": "Auth",
                "description": "Authentication endpoints"
            },
            {
                "name": "Health",
                "description": "Health and monitoring"
            }
        ],
        servers=[
            {"url": "http://localhost:8080", "description": "Development server"},
            {"url": "https://api.screen2deck.com", "description": "Production server"}
        ],
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT authentication token"
        },
        "ApiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key authentication"
        }
    }
    
    # Add example schemas
    openapi_schema["components"]["examples"] = {
        "UploadSuccess": {
            "summary": "Successful upload",
            "value": {
                "jobId": "550e8400-e29b-41d4-a716-446655440000",
                "message": "Image uploaded successfully"
            }
        },
        "DeckResult": {
            "summary": "OCR result",
            "value": {
                "jobId": "550e8400-e29b-41d4-a716-446655440000",
                "raw": {
                    "spans": [
                        {"text": "4 Lightning Bolt", "conf": 0.95},
                        {"text": "4 Counterspell", "conf": 0.92}
                    ],
                    "mean_conf": 0.93
                },
                "parsed": {
                    "main": [
                        {"qty": 4, "name": "Lightning Bolt", "candidates": []},
                        {"qty": 4, "name": "Counterspell", "candidates": []}
                    ],
                    "side": []
                },
                "normalized": {
                    "main": [
                        {"qty": 4, "name": "Lightning Bolt", "scryfall_id": "abc123"},
                        {"qty": 4, "name": "Counterspell", "scryfall_id": "def456"}
                    ],
                    "side": []
                },
                "timings_ms": {
                    "preprocess": 150,
                    "ocr": 850,
                    "scryfall": 200,
                    "total": 1200
                }
            }
        },
        "ErrorResponse": {
            "summary": "Error response",
            "value": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input",
                    "details": {
                        "field": "image",
                        "reason": "File too large"
                    }
                }
            }
        }
    }
    
    # Add webhook definitions
    openapi_schema["webhooks"] = {
        "jobComplete": {
            "post": {
                "requestBody": {
                    "description": "Job completion notification",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/DeckResult"
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Webhook received"
                    }
                }
            }
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

def setup_api_docs(app: FastAPI):
    """Setup API documentation endpoints."""
    
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png"
        )
    
    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
            redoc_favicon_url="https://fastapi.tiangolo.com/img/favicon.png"
        )
    
    # Custom OpenAPI schema
    app.openapi = lambda: custom_openapi(app)