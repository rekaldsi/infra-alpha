# InfraAlpha Portal — Security Model

## Required Environment Variables

| Variable | Purpose | How to Generate |
|---|---|---|
| `SUPABASE_SERVICE_KEY` | Supabase service-role JWT for database access | Copy from Supabase project → Settings → API → `service_role` key |
| `PORTAL_API_TOKEN` | Bearer token protecting all `/api/accounts/*` routes | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ALPACA_ENCRYPTION_KEY` | Fernet key for encrypting Alpaca API credentials at rest | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins | e.g. `https://infra-alpha.up.railway.app,https://yourapp.com` |

All variables are **required** — the server will refuse to start if `SUPABASE_SERVICE_KEY`, `PORTAL_API_TOKEN`, or `ALPACA_ENCRYPTION_KEY` are missing.

---

## Security Model Overview

### Encryption at Rest
Alpaca API key IDs and secrets are encrypted using Fernet symmetric encryption (`alpaca_crypto.py`) before being written to `data/trader_accounts.json`. The encryption key is never stored alongside the data — it lives only in `ALPACA_ENCRYPTION_KEY`.

### API Authentication Layer
All `/api/accounts/*` endpoints require a `Authorization: Bearer <token>` header matching `PORTAL_API_TOKEN`. Public market data endpoints (`/api/macro`, `/api/quotes`, `/api/vwap-scan`, etc.) are intentionally unauthenticated since they contain no sensitive data.

Clients must include:
```
Authorization: Bearer <PORTAL_API_TOKEN>
```

### Rate Limiting
The `/api/accounts/<user>/connect` endpoint is rate-limited to **5 attempts per user per 60 seconds** using an in-memory sliding window. Returns `429 Too Many Requests` when exceeded.

### Input Validation
- `user_name` URL parameters are validated against a whitelist (`VALID_USERS = {"jerry", "frank"}`). Unknown users receive `404`.
- Request body size is capped at **16KB** (`MAX_CONTENT_LENGTH`).
- Ticker symbols are sanitized to alphanumeric + `.^` characters only.

### CORS Restriction
CORS is restricted to origins listed in `ALLOWED_ORIGINS`. Defaults to `http://localhost:8083` for local dev. Set explicitly in production.

### Security Headers
Every response includes:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Cache-Control: no-store`

### Error Handling
Unhandled exceptions are logged server-side with full stack traces but return only `{"error": "Internal server error"}` to clients — no stack trace leakage.

---

## Files That Must Never Be Committed
- `data/trader_accounts.json` — contains encrypted Alpaca credentials
- `.env` / `*.env` — contains all secrets

Both are listed in `.gitignore`.
