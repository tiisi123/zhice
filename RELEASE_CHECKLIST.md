# Release Checklist — v0.1.0-rc1

## Pre-Release Validation

- [x] `npm run lint` — 0 errors, 0 warnings
- [x] `npm run typecheck` — clean
- [x] `npm run test` — 22/22 unit tests passed
- [x] `npm run test:e2e` — 28/28 Playwright E2E tests passed
- [x] `npm run build` — production bundle built successfully
- [x] Git working tree clean (only runtime DB/cache files unstaged)

## Release Artifacts

- [x] Release branch: `release/v0.1.0-rc1`
- [x] CHANGELOG.md created
- [x] DEPLOYMENT.md created
- [x] ENVIRONMENT.md created
- [x] RELEASE_CHECKLIST.md created (this file)
- [ ] Release docs committed
- [ ] Tag `v0.1.0-rc1` created locally
- [ ] Pushed to remote (requires SSH key — manual step)

## Deployment Steps

### From a machine with Gitee SSH key:

```bash
git push origin release/v0.1.0-rc1
git push origin v0.1.0-rc1
```

### On staging host:

```bash
cd /opt/zhice
git fetch origin
git checkout v0.1.0-rc1
make deploy-init          # First time only
cp deploy/.env.example deploy/.env
chmod 600 deploy/.env
# Edit deploy/.env with production values (see ENVIRONMENT.md)
make deploy-up
make deploy-ps            # Verify all 4 services healthy
curl -fsS http://localhost/api/health
```

## Included Milestones

| Milestone | Scope | Status |
|-----------|-------|--------|
| M001 | Deployment foundation + data contract | Complete |
| M002 | 5xx alerting + email notifications | Complete |
| M003 | AI research engine (6 agents, 7 features) | Complete |
| M004 | Frontend analysis panels | Complete |
| M007/S01-S03 | Quality hardening (tests, lint, E2E) | Complete |

## Deferred to Post-RC

| Item | Reason |
|------|--------|
| M007/S04 | Bundle size baseline + optimization |
| M007/S05 | Error boundaries + frontend observability |
| M007/S06 | Full M007 quality closure |
| Real payment integration | Mock-only in v0.1.0 |
| KPL cookie auto-refresh | Requires API restart after admin update |

## Known Limitations

1. **Payment is mock-only** — CheckoutPage exists but processes no real transactions
2. **Single worker** — No horizontal scaling; in-memory rate-limit/cache, no Redis
3. **KPL cookie** — Admin cookie update requires API container restart
4. **TuShare batch** — Financial indicators require per-stock API calls
5. **ICP beian** — Required for mainland China before Caddy can provision HTTPS cert
6. **Bundle size** — antd (436 KB gzip) and echarts (365 KB gzip) are large; optimization deferred to S04

## Security Verification

Before deploying to production, verify all items in DEPLOYMENT.md "Security Pre-Launch Checklist" (11 items).

## Post-Deployment Smoke Test

```bash
# On staging host after deploy
curl -fsS https://YOUR_DOMAIN/api/health
curl -fsS https://YOUR_DOMAIN/ | grep -q '<div id="root">'

# From browser
# 1. Open https://YOUR_DOMAIN/login — login form renders
# 2. Login with admin / ZHICE_ADMIN_PASSWORD (the value set in deploy/.env)
#    — redirects to /replay
# 3. Navigate sidebar — all protected pages load
# 4. Check /admin — invite codes, KPL cookie, health panels render
```

The admin account is auto-created at first startup with username `admin` and the password from `ZHICE_ADMIN_PASSWORD`. Change the password after first login via the admin panel.
