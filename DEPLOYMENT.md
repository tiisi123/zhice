# Deployment Guide

## Architecture

```
Internet → Caddy (TLS, :443/:80) → Nginx (SPA, :80) → FastAPI/gunicorn (:8000) → MySQL 8.0 (:3306)
```

Four Docker Compose services on a single host (4C8G minimum):

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `zhice-db` | mysql:8.0 | 3306 (internal) | Database, utf8mb4_0900_ai_ci, UTC |
| `zhice-api` | custom (Python 3.11) | 8000 (internal) | FastAPI + gunicorn, 1 worker |
| `zhice-web` | custom (Nginx 1.27) | 80 (internal) | React SPA, proxies /api to zhice-api |
| `caddy` | caddy:2.8-alpine | 80, 443 (host) | TLS termination, Let's Encrypt |

## Prerequisites

- Ubuntu 22.04 LTS (or compatible)
- Docker Engine 24+ with compose plugin
- Dedicated deploy user with docker group access
- Timezone set to UTC
- UFW configured: allow 22, 80, 443

For mainland China: ICP beian is required before Caddy can provision a certificate for a `.cn` domain (7–20 business days).

## First Deployment

### 1. Clone

```bash
ssh deploy@YOUR_HOST
sudo mkdir -p /opt/zhice && sudo chown deploy:deploy /opt/zhice
git clone YOUR_REPO_URL /opt/zhice
cd /opt/zhice
```

### 2. Initialize host directories

```bash
make deploy-init
```

Creates `/var/log/zhice` owned by uid 10001 (the container user). Without this, the API container fails on startup with a `PermissionError`.

### 3. Configure environment

```bash
cp deploy/.env.example deploy/.env
chmod 600 deploy/.env
# Edit deploy/.env with production values
```

Required variables — see [ENVIRONMENT.md](ENVIRONMENT.md) for the full reference:

| Variable | How to generate |
|----------|----------------|
| `ZHICE_JWT_SECRET` | `openssl rand -hex 32` |
| `ZHICE_ADMIN_PASSWORD` | Choose a strong password, change after first login |
| `DATABASE_URL` | `mysql+pymysql://root:YOUR_MYSQL_PWD@zhice-db:3306/zhice` |
| `MYSQL_ROOT_PASSWORD` | Must match the password in DATABASE_URL |
| `ENCRYPTION_KEY` | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `STAGING_DOMAIN` | Your domain (e.g. `staging.zhice.com`) or `:80` for HTTP-only |

Plus at least one data source key (KPL or TuShare) and one AI key (Anthropic or OpenAI).

### 4. Start the stack

```bash
make deploy-up
```

This runs `docker compose up -d --build`, which:
1. Builds zhice-api and zhice-web images
2. Starts MySQL and waits for healthy
3. Runs `alembic upgrade head` (creates 27 tables)
4. Starts the API server with healthcheck
5. Starts Nginx serving the SPA
6. Starts Caddy for TLS termination

### 5. Verify

```bash
make deploy-ps          # All 4 services should show "healthy"
curl -fsS http://localhost/api/health
```

## Operations

### Make Targets

| Target | Purpose |
|--------|---------|
| `make deploy-up` | Start/rebuild stack |
| `make deploy-down` | Stop stack, preserve data |
| `make deploy-down-clean` | Stop + wipe MySQL data and Caddy certs |
| `make deploy-logs` | Tail all services |
| `make deploy-logs-api` | Tail API only (primary troubleshooting) |
| `make deploy-ps` | Show health status |
| `make deploy-shell-api` | Shell into API container |
| `make deploy-shell-db` | MySQL client shell |
| `make deploy-rebuild` | Force no-cache rebuild |

### Updating Code

```bash
cd /opt/zhice
git pull origin main
make deploy-up
```

The API entrypoint runs `alembic upgrade head` on every start, so schema migrations apply automatically.

### Auto-Deploy (CI/CD)

The `deploy-staging.yml` workflow auto-deploys on push to main when `DEPLOY_ENABLED` is `true`.

Configure in GitHub:
- **Secrets**: `STAGING_HOST`, `STAGING_USER`, `STAGING_SSH_KEY`, `STAGING_PORT`
- **Variable**: `DEPLOY_ENABLED` = `true`

### Log Locations

| Log | Location |
|-----|----------|
| API application | `/var/log/zhice/api.log` |
| API access | `/var/log/zhice/api-access.log` |
| Caddy general | `/var/log/zhice/caddy.log` |
| Caddy access | `/var/log/zhice/caddy-access.log` |
| Docker logs | `docker compose logs <service>` |

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| API container restart loop | Missing `/var/log/zhice` with uid 10001 ownership | `make deploy-init` |
| API refuses to start | Missing mandatory env vars | Check ENVIRONMENT.md, ensure all 4 mandatory vars set |
| MySQL connection refused | MYSQL_ROOT_PASSWORD doesn't match DATABASE_URL | Align passwords in deploy/.env |
| Caddy cert failure | DNS not pointing to host, ports 80/443 blocked, or ICP beian missing | Check DNS, UFW rules, beian status |
| `alembic upgrade head` fails | Schema conflict from manual DB changes | `make deploy-shell-db`, inspect tables, consider `make deploy-down-clean` for fresh start |
| Stale frontend after update | Docker image cache | `make deploy-rebuild` |

## Security Pre-Launch Checklist

1. `ZHICE_JWT_SECRET` is a unique 64-char hex (not a default)
2. `DEBUG=false`
3. `CORS_ORIGINS` restricted to production domain only
4. `deploy/.env` is `chmod 600`, owned by deploy user
5. Admin password changed after first login
6. Swagger UI disabled in production (automatic when DEBUG=false)
7. No mock=True in production API responses
8. `.env` is not committed to git
9. Payment entry point closed (mock-only in v0.1.0)
10. SSH key auth only (password auth disabled)
11. UFW: only ports 22, 80, 443 open
