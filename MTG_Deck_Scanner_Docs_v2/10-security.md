# Security

- **No PII** stored; in-memory job store by default.
- Limit upload size via `MAX_IMAGE_MB` (413).
- Validate content-type and decoding; reject unknown mimetypes.
- Simple rate-limit; consider Redis-based distributed limit for prod.
- CORS: lock to frontend domain(s) in production.
- TLS termination via Nginx/Traefik.
- Logs are JSON, avoid raw image contents; include `traceId` and `jobId` only.
