# Environment Variables

Reference for all environment variables used by zhice v0.1.0-rc1.

See `deploy/.env.example` for a copy-pasteable template.

## Mandatory (Startup Validation)

These four variables are **required** when `DEBUG=false` (production mode). The API server refuses to start without them.

| Variable | Format | Example |
|----------|--------|---------|
| `ZHICE_JWT_SECRET` | 64-char hex | `openssl rand -hex 32` |
| `ZHICE_ADMIN_PASSWORD` | String, change after first login | `ChangeMeN0w!` |
| `DATABASE_URL` | mysql+pymysql URI | `mysql+pymysql://root:PASS@zhice-db:3306/zhice` |
| `ENCRYPTION_KEY` | Fernet 32-byte base64 | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

`DATABASE_URL` must use `mysql` or `mysql+pymysql` scheme. SQLite is rejected in production mode.

## MySQL

| Variable | Purpose | Default |
|----------|---------|---------|
| `MYSQL_ROOT_PASSWORD` | Root password for zhice-db container | *(required)* |

Must match the password in `DATABASE_URL`.

## Deployment

| Variable | Purpose | Default |
|----------|---------|---------|
| `STAGING_DOMAIN` | Domain for Caddy TLS (e.g. `staging.zhice.com`) | `:80` (HTTP-only, no ACME) |
| `DEBUG` | Debug mode: `true` downgrades missing-key errors to warnings | `false` |
| `CORS_ORIGINS` | JSON array of allowed origins | `["http://localhost:5173","http://localhost:3000"]` |

## Data Sources

At least one data source is required for live data. Without any, pages show fallback/empty state.

### KPL (Short-Line Primary)

| Variable | Purpose |
|----------|---------|
| `KPL_USER_ID` | KPL account user ID |
| `KPL_TOKEN` | KPL API token |
| `KPL_DEVICE_ID` | Device identifier (has a default UUID) |

### TuShare

| Variable | Purpose |
|----------|---------|
| `TUSHARE_TOKEN` | TuShare Pro API token |

### Other Sources (Optional)

| Variable | Purpose | Note |
|----------|---------|------|
| `THS_COOKIE` | THS web cookie | Short-lived, refresh periodically |
| `DFCF_COOKIE` | East Money cookie | Short-lived, refresh periodically |
| `JYGS_TOKEN` | JYGS API token | |
| `JYGS_SESSION` | JYGS session ID | |

## AI

At least one AI provider key is required for AI Agent features.

| Variable | Purpose | Default |
|----------|---------|---------|
| `PREFERRED_AI_API_KEY` | Product AI key for OpenAI-compatible gateways | |
| `PREFERRED_AI_BASE_URL` | Product AI gateway base URL | `https://cc.maya.today/api/v1` |
| `PREFERRED_AI_CHAT_MODEL` | Product chat model | `gpt-4o` |
| `PREFERRED_AI_FAST_MODEL` | Product fast model | `gpt-4o-mini` |
| `DEEPSEEK_API_KEY` | Product DeepSeek API key | |
| `DEEPSEEK_BASE_URL` | DeepSeek API base URL | `https://api.deepseek.com` |
| `ZHICE_AI_ANTHROPIC_API_KEY` | Product-scoped Anthropic Claude API key | |
| `ZHICE_AI_ANTHROPIC_BASE_URL` | Product-scoped Anthropic API base URL | `https://api.anthropic.com` |
| `ZHICE_AI_OPENAI_API_KEY` | Product-scoped OpenAI API key | |

The product backend intentionally ignores generic `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` so local IDE/agent API credentials are not consumed by 智策.

## SMTP (Optional)

5xx alert emails. If not configured, alert emails are silently skipped.

| Variable | Purpose | Default |
|----------|---------|---------|
| `SMTP_HOST` | SMTP server hostname | |
| `SMTP_PORT` | SMTP server port | `465` |
| `SMTP_USER` | SMTP username | |
| `SMTP_PASS` | SMTP password | |

## Frontend Build

| Variable | Purpose | Default |
|----------|---------|---------|
| `VITE_API_PORT` | API port for dev server proxy | `8000` |

Only used during `npm run dev`. Not needed in production (Nginx proxies internally).

## CI/CD (GitHub Actions Secrets)

| Secret/Variable | Purpose |
|-----------------|---------|
| `STAGING_HOST` | Staging server IP/hostname |
| `STAGING_USER` | SSH user for deploy |
| `STAGING_SSH_KEY` | SSH private key (ed25519) |
| `STAGING_PORT` | SSH port (default: 22) |
| `DEPLOY_ENABLED` | Repository variable — set to `true` to enable auto-deploy on push |

## Security Notes

- `.env` is in `.gitignore` — never commit secrets
- `deploy/.env` on staging host should be `chmod 600`
- CI injects secrets via GitHub Actions Secrets, never hardcoded
- Startup validator only prints key *names* on error, never values
- `docker compose logs` does not print env values
