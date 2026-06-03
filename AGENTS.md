# AGENTS.md

## Cursor Cloud specific instructions

### Product overview

NexusQuant is a two-app monorepo: **backend** (FastAPI on port 8000) and **frontend** (Vite/React on port 5173). PostgreSQL and Redis are required infrastructure services.

### Infrastructure (PostgreSQL + Redis)

Start infra with Docker Compose from the repo root:

```bash
sudo docker compose up -d postgres redis
```

In this Cloud VM, Docker requires `sudo`. If the daemon is not running, start it first:

```bash
sudo dockerd > /tmp/dockerd.log 2>&1 &
```

Default connection strings (also the backend defaults in `backend/app/core/config.py`):

- Postgres: `postgresql://postgres:postgres@localhost:5432/nexusquant`
- Redis: `redis://localhost:6379/0`

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Note:** Ubuntu requires the `python3.12-venv` system package before `python3 -m venv` works. This is a one-time VM setup step, not part of the update script.

There is no committed `.env.example`; local dev works with pydantic defaults. Upstox credentials (`UPSTOX_ACCESS_TOKEN`, etc.) are optional — without them the app runs in **SAFE MODE** (expected for dev without broker access).

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Optional env: `VITE_BACKEND_URL` (defaults to `http://localhost:8000`).

### Lint / test / build

This repo has **no** dedicated lint or test scripts. Use these checks:

| Check | Command |
|-------|---------|
| Frontend typecheck + build | `cd frontend && npm run build` |
| Backend health | `curl http://localhost:8000/api/health` |
| Telemetry REST | `curl http://localhost:8000/api/telemetry/latest` |
| Telemetry WebSocket | `ws://localhost:8000/api/ws/telemetry` |

### Gotchas

- **DB schema**: Tables are created automatically on backend startup via `StateStore.connect()` (`CREATE TABLE IF NOT EXISTS`).
- **SAFE MODE is normal** without Upstox credentials: broker shows disconnected, trading disabled.
- Backend logs will show Upstox authorize warnings when `UPSTOX_ACCESS_TOKEN` is empty — this is expected.
- README references `cp .env.example .env` but those files are not in the repo; defaults in `config.py` suffice for local dev.
- Long-running dev servers should be started in tmux sessions (e.g. `backend-uvicorn`, `frontend-vite`).

See `README.md` for full API list and deployment docs.
