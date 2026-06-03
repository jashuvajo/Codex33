# AGENTS.md

## Cursor Cloud specific instructions

### Product overview

NexusQuant is a full-stack AI scalping terminal (FastAPI backend + Vite/React frontend). See `README.md` for architecture and env vars.

### Services (local dev)

| Service | Port | Start |
|---------|------|--------|
| PostgreSQL 16 | 5432 | `sudo docker compose up -d postgres` |
| Redis 7 | 6379 | `sudo docker compose up -d redis` |
| Backend (Uvicorn) | 8000 | `cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |
| Frontend (Vite) | 5173 | `cd frontend && npm run dev -- --host 0.0.0.0 --port 5173` |

Docker requires `sudo` in this VM (`dockerd` runs as root). Use `fuse-overlayfs` storage driver (already configured in `/etc/docker/daemon.json`).

### Non-obvious gotchas

- **python3-venv**: Ubuntu images may need `sudo apt install python3.12-venv` before `python -m venv`.
- **backend/.env**: Not committed. Copy vars from `README.md` (there is no `.env.example` in repo despite README mentioning it). Minimum for boot: `REDIS_URL` and `POSTGRES_DSN` pointing at Docker Compose services.
- **SAFE MODE**: Without `UPSTOX_ACCESS_TOKEN`, broker stays disconnected and trading/signals stay disabled — this is expected, not a setup failure.
- **DB schema**: Tables are created automatically on backend startup via `StateStore.connect()` (`CREATE TABLE IF NOT EXISTS`).
- **No lint/test scripts**: Repo has no ESLint, Ruff, or pytest configuration; validate with `npm run build` (frontend) and `curl http://localhost:8000/api/health` (backend).

### Quick verification

```bash
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/telemetry/latest
cd frontend && npm run build
```

### Upstox (optional for live data)

Set `UPSTOX_ACCESS_TOKEN` (and optionally `UPSTOX_CLIENT_ID`, `UPSTOX_REDIRECT_URI`) in `backend/.env` for live NIFTY/SENSEX feed during market hours.
