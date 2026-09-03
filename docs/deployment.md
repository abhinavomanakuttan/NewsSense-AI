# Deployment Guide

## Prerequisites

- Docker 24+
- Docker Compose 2.20+
- 8GB+ RAM (16GB recommended)
- 50GB+ disk space
- Domain name (for production)

## Quick Deploy

```bash
# Clone and setup
git clone <repo> && cd smartfeed-ai
cp .env.example .env
# Edit .env with your secrets

# Start all services
cd infra
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head

# Seed data
docker-compose exec backend python scripts/seed.py
```

## Production Deployment

### 1. Environment Variables

Set these in `.env`:
```bash
SECRET_KEY=<random-64-char-string>
JWT_SECRET_KEY=<random-64-char-string>
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=https://yourdomain.com
```

### 2. SSL/TLS

Use Let's Encrypt with Certbot:

```bash
docker-compose run --rm certbot certonly --webroot \
  -w /var/www/certbot \
  -d yourdomain.com
```

### 3. Scaling

```bash
# Scale workers
docker-compose up -d --scale celery_worker=4

# Scale backend
docker-compose up -d --scale backend=3
```

### 4. Monitoring

The backend exposes Prometheus metrics at `GET /metrics` (path-normalized,
see `docs/monitoring.md` for the full metric list and dashboard setup).

Access:
- Grafana: http://localhost:3001 (admin/admin) — "SmartFeed Backend" dashboard auto-provisioned
- Prometheus: http://localhost:9090
- RabbitMQ: http://localhost:15672 (guest/guest)

### 5. Backup

```bash
# Automated backup
docker-compose exec infra/scripts/backup.sh

# Restore
gunzip < backup.sql.gz | docker-compose exec -T postgres psql -U smartfeed smartfeed
```

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/`):
1. `ci.yml` — lint, formatting, and tests on every push/PR:
   - Backend: ruff check + format, full pytest suite against PostgreSQL 16 + Redis, coverage uploaded to Codecov
   - Frontend: ESLint, typecheck, Prettier check, Jest tests
2. `cd.yml` — builds Docker images on main branch, pushes to GitHub Container Registry, deploys to production server via SSH

## System Requirements

| Environment | CPU   | RAM  | Disk  |
|-------------|-------|------|-------|
| Development | 4 core| 8GB  | 20GB  |
| Production  | 8 core| 16GB | 100GB |
| Enterprise  | 16core| 32GB | 500GB |
