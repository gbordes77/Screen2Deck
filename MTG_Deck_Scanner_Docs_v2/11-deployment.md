# Deployment

## Docker Compose (dev/prod single host)
```
docker compose up --build -d
```

## Reverse proxy
- Nginx/Traefik in front of `webapp:3000` and `backend:8080`.
- Set `client_max_body_size 10M;` (or similar) for uploads.

## Redis (optional)
- Set `USE_REDIS=true` and `REDIS_URL` for shared job store and distributed rate limiting.

## CORS
- Restrict to your public frontend origin(s).

## Observability
- Consume JSON logs; index by `traceId`, `jobId`.
