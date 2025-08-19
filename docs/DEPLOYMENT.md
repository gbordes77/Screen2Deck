# Screen2Deck Deployment Guide (v2.3.0 - ONLINE-ONLY)

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Development Deployment](#development-deployment)
3. [Production Deployment](#production-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Provider Guides](#cloud-provider-guides)
6. [Configuration](#configuration)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements
- **CPU**: 2+ cores (4+ recommended for production)
- **RAM**: 4GB minimum (8GB+ recommended)
- **Storage**: 10GB minimum (EasyOCR models ~64MB downloaded on first run)
- **OS**: Linux (Ubuntu 20.04+), macOS, Windows with WSL2
- **Internet**: REQUIRED - System operates 100% online

### Software Requirements
- Docker 20.10+
- Docker Compose 2.0+
- Kubernetes 1.24+ (for K8s deployment)
- kubectl CLI
- Helm 3.0+ (optional)

## Development Deployment

### Quick Start with Docker Compose

```bash
# Clone repository
git clone https://github.com/gbordes77/Screen2Deck.git
cd Screen2Deck

# Start services (ONLINE mode)
make up
# Or with Docker Compose:
docker-compose --profile core up -d

# Note: First OCR request will download EasyOCR models (~64MB)
# Models are cached in container at /root/.EasyOCR/

# Test online connectivity
make test-online

# View logs
make logs
# Or: docker-compose logs -f backend

# Stop services
make down
# Or: docker-compose down
```

### Local Development Setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_scryfall.py
uvicorn app.main:app --reload

# Frontend
cd webapp
npm install
npm run dev

# Services
redis-server
celery -A app.tasks worker --loglevel=info
```

## Production Deployment

### 1. Prepare Environment

```bash
# Create production directory
mkdir -p /opt/screen2deck
cd /opt/screen2deck

# Clone repository
git clone https://github.com/gbordes77/Screen2Deck.git .

# Create secrets
openssl rand -base64 32 > jwt_secret.txt
```

### 2. Configure Production Settings

Create `.env.production`:

```env
# Application
APP_ENV=production
DEBUG=false
ALLOWED_HOSTS=api.screen2deck.com

# Security
JWT_SECRET_KEY=$(cat jwt_secret.txt)
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL=postgresql://screen2deck:${DB_PASSWORD}@postgres:5432/screen2deck
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_POOL_SIZE=10

# Rate Limiting
RATE_LIMIT_PER_MINUTE=30
RATE_LIMIT_PER_IP=10

# OCR
OPENAI_API_KEY=${OPENAI_API_KEY}  # Optional
MAX_UPLOAD_SIZE=10485760

# Monitoring
OTLP_ENDPOINT=otel-collector:4317
LOG_LEVEL=INFO
```

### 3. Build and Deploy

```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Run database migrations
docker-compose exec backend alembic upgrade head

# Create initial admin user
docker-compose exec backend python -c "
from app.db.database import get_db
from app.db.models import User
from app.auth import hash_password
import asyncio

async def create_admin():
    async with get_db() as db:
        admin = User(
            username='admin',
            email='admin@screen2deck.com',
            hashed_password=hash_password('changeme'),
            is_admin=True
        )
        db.add(admin)
        await db.commit()

asyncio.run(create_admin())
"
```

### 4. Setup Reverse Proxy (Nginx)

```nginx
# /etc/nginx/sites-available/screen2deck
server {
    listen 80;
    server_name api.screen2deck.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.screen2deck.com;

    ssl_certificate /etc/letsencrypt/live/api.screen2deck.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.screen2deck.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # API backend
    location /api {
        proxy_pass http://localhost:8080;
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
    }

    # WebSocket
    location /ws {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name screen2deck.com www.screen2deck.com;
    return 301 https://screen2deck.com$request_uri;
}

server {
    listen 443 ssl http2;
    server_name screen2deck.com www.screen2deck.com;

    ssl_certificate /etc/letsencrypt/live/screen2deck.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/screen2deck.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Kubernetes Deployment

### 1. Prerequisites

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Configure kubectl
export KUBECONFIG=/path/to/kubeconfig
```

### 2. Deploy to Kubernetes

```bash
# Create namespace
kubectl create namespace screen2deck

# Create secrets
kubectl create secret generic screen2deck-secrets \
  --from-literal=database-url="postgresql://user:pass@postgres:5432/screen2deck" \
  --from-literal=redis-url="redis://redis:6379/0" \
  --from-literal=jwt-secret="$(openssl rand -base64 32)" \
  -n screen2deck

# Deploy application
kubectl apply -f k8s/ -n screen2deck

# Check deployment status
kubectl get pods -n screen2deck
kubectl get svc -n screen2deck

# Port forward for testing
kubectl port-forward svc/webapp 3000:3000 -n screen2deck
```

### 3. Configure Ingress

```yaml
# k8s/ingress-tls.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: screen2deck-tls
  namespace: screen2deck
spec:
  secretName: screen2deck-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - screen2deck.com
  - api.screen2deck.com
```

### 4. Horizontal Pod Autoscaling

```bash
# Enable metrics server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Check HPA status
kubectl get hpa -n screen2deck

# Manual scaling
kubectl scale deployment backend --replicas=5 -n screen2deck
```

## Cloud Provider Guides

### AWS EKS

```bash
# Create EKS cluster
eksctl create cluster \
  --name screen2deck \
  --region us-east-1 \
  --nodegroup-name workers \
  --node-type t3.medium \
  --nodes 3

# Install AWS Load Balancer Controller
kubectl apply -k "github.com/aws/eks-charts/stable/aws-load-balancer-controller/crds"
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=screen2deck

# Deploy application
kubectl apply -f k8s/
```

### Google GKE

```bash
# Create GKE cluster
gcloud container clusters create screen2deck \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type n1-standard-2

# Get credentials
gcloud container clusters get-credentials screen2deck

# Deploy application
kubectl apply -f k8s/
```

### Azure AKS

```bash
# Create resource group
az group create --name screen2deck-rg --location eastus

# Create AKS cluster
az aks create \
  --resource-group screen2deck-rg \
  --name screen2deck \
  --node-count 3 \
  --generate-ssh-keys

# Get credentials
az aks get-credentials --resource-group screen2deck-rg --name screen2deck

# Deploy application
kubectl apply -f k8s/
```

### DigitalOcean Kubernetes

```bash
# Create cluster via CLI
doctl kubernetes cluster create screen2deck \
  --region nyc1 \
  --size s-2vcpu-4gb \
  --count 3

# Save kubeconfig
doctl kubernetes cluster kubeconfig save screen2deck

# Deploy application
kubectl apply -f k8s/
```

## Configuration

### Environment Variables Reference

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `APP_ENV` | Environment (development/production) | development | No |
| `JWT_SECRET_KEY` | JWT signing key (min 32 chars) | - | Yes |
| `DATABASE_URL` | PostgreSQL connection string | - | Yes |
| `REDIS_URL` | Redis connection string | redis://localhost:6379/0 | No |
| `OPENAI_API_KEY` | OpenAI API key for Vision | - | No |
| `RATE_LIMIT_PER_MINUTE` | Rate limit per authenticated user | 30 | No |
| `MAX_UPLOAD_SIZE` | Maximum upload size in bytes | 10485760 | No |
| `OTLP_ENDPOINT` | OpenTelemetry collector endpoint | localhost:4317 | No |
| `LOG_LEVEL` | Logging level | INFO | No |

### Database Setup

```sql
-- Create database
CREATE DATABASE screen2deck;
CREATE USER screen2deck WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE screen2deck TO screen2deck;

-- Enable extensions
\c screen2deck
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```

### Redis Configuration

```conf
# /etc/redis/redis.conf
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

## Monitoring & Maintenance

### Health Checks

```bash
# Check application health
curl https://api.screen2deck.com/health

# Check metrics
curl https://api.screen2deck.com/metrics

# Check pod status
kubectl get pods -n screen2deck
kubectl describe pod <pod-name> -n screen2deck
```

### Logging

```bash
# View application logs
kubectl logs -f deployment/backend -n screen2deck

# View all logs
kubectl logs -f -l app=backend -n screen2deck --all-containers=true

# Export logs
kubectl logs deployment/backend -n screen2deck > backend.log
```

### Backup & Restore

```bash
# Backup database
kubectl exec -it postgres-0 -n screen2deck -- \
  pg_dump -U screen2deck screen2deck > backup.sql

# Restore database
kubectl exec -i postgres-0 -n screen2deck -- \
  psql -U screen2deck screen2deck < backup.sql

# Backup Redis
kubectl exec -it redis-0 -n screen2deck -- \
  redis-cli BGSAVE

# Copy backup files
kubectl cp screen2deck/redis-0:/data/dump.rdb ./redis-backup.rdb
```

### Updates & Maintenance

```bash
# Update application
git pull origin main
docker-compose build
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head

# Restart services
docker-compose restart

# Clean up old images
docker image prune -a -f
```

## Troubleshooting

### Common Issues

#### Database Connection Failed
```bash
# Check database status
kubectl exec -it postgres-0 -n screen2deck -- psql -U screen2deck -c "SELECT 1"

# Check connection string
kubectl get secret screen2deck-secrets -n screen2deck -o yaml
```

#### Redis Connection Failed
```bash
# Check Redis status
kubectl exec -it redis-0 -n screen2deck -- redis-cli ping

# Clear Redis cache
kubectl exec -it redis-0 -n screen2deck -- redis-cli FLUSHALL
```

#### High Memory Usage
```bash
# Check memory usage
kubectl top pods -n screen2deck

# Restart pods
kubectl rollout restart deployment/backend -n screen2deck
```

#### OCR Processing Slow
```bash
# Check Celery workers
kubectl logs -f deployment/celery-worker -n screen2deck

# Scale workers
kubectl scale deployment celery-worker --replicas=3 -n screen2deck
```

### Debug Mode

```bash
# Enable debug logging
kubectl set env deployment/backend LOG_LEVEL=DEBUG -n screen2deck

# Port forward for debugging
kubectl port-forward deployment/backend 8080:8080 -n screen2deck

# Execute shell in container
kubectl exec -it deployment/backend -n screen2deck -- /bin/bash
```

### Performance Tuning

```bash
# Adjust resource limits
kubectl edit deployment backend -n screen2deck

# Update HPA settings
kubectl edit hpa backend-hpa -n screen2deck

# Monitor performance
kubectl top nodes
kubectl top pods -n screen2deck
```

## Security Considerations

### SSL/TLS Setup

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@screen2deck.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

### Network Policies

```yaml
# k8s/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-policy
  namespace: screen2deck
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: webapp
    - podSelector:
        matchLabels:
          app: nginx
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    - podSelector:
        matchLabels:
          app: redis
```

### Secret Management

```bash
# Use sealed-secrets
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# Create sealed secret
echo -n "mysecret" | kubectl create secret generic mysecret \
  --dry-run=client \
  --from-file=secret=/dev/stdin \
  -o yaml | kubeseal -o yaml > sealed-secret.yaml
```

## Support

For deployment issues:
- GitHub Issues: https://github.com/gbordes77/Screen2Deck/issues
- Documentation: https://screen2deck.com/docs
- Community Discord: https://discord.gg/screen2deck