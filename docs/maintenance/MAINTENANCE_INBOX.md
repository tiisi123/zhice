# Maintenance Inbox

Items discovered during RC testing or operations that should be addressed in future milestones.

## M008 — Post-RC Hardening

### Non-blocking (P3)

- [ ] **Replace Vite dev server with production build** — Current external access uses Vite dev server on port 3001. For production deployment, switch to built static assets served by Nginx/Caddy (deploy/ already has this config).
- [ ] **Add TLS** — External access is plaintext HTTP. Production deployment should use HTTPS via Caddy auto-TLS or a reverse proxy with certificates.
- [ ] **Manual browser verification** — React rendering, Ant Design charts, form interactions, and WebSocket features have not been verified via browser. Recommend a manual walkthrough of all pages.
