# NexusQuant

NexusQuant is an institutional-style AI scalping terminal focused on:

- NIFTY
- SENSEX

Stack:

- Frontend: React + Tailwind (Vite)
- Backend: FastAPI + asyncio + WebSocket
- Infra: Redis + PostgreSQL
- Broker/Data: Upstox REST + MarketDataStreamerV3

## Critical safety rule

Trading and AI signals are disabled unless all are true:

1. Upstox REST health is successful
2. Upstox live market stream is connected
3. Feed freshness checks pass

If any check fails:

- broker disconnected state
- trading/signals disabled
- SAFE MODE enabled automatically

## Local run

```bash
docker compose up -d postgres redis

cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## API

- `GET /api/health`
- `GET /api/telemetry/latest`
- `GET /api/analysis/session`
- `GET /api/analysis/closed-market`
- `GET /api/journal/trades`
- `GET /api/metrics`
- `WS /api/ws/telemetry`

## Deploy on Railway

This repo is ready for Railway as two services in one project.

### 1) Create a Railway project

- In Railway, click **New Project** -> **Deploy from GitHub repo**
- Select this repository

### 2) Add backend service

- Create a service from this repo
- Set **Root Directory** to `backend`
- Railway will use:
  - `backend/Dockerfile`
  - `backend/railway.json`

Add backend env vars:

- `UPSTOX_ACCESS_TOKEN`
- `UPSTOX_CLIENT_ID`
- `UPSTOX_REDIRECT_URI`
- `INSTRUMENT_KEYS` (optional override)
- `TELEMETRY_INTERVAL_SECONDS` (optional)
- `STALE_FEED_SECONDS` (optional)

Create and attach Railway Postgres + Redis plugins.

The backend supports Railway-native names automatically:

- Postgres: `DATABASE_URL` (or `DATABASE_PRIVATE_URL`)
- Redis: `REDIS_URL` (or `REDIS_PRIVATE_URL`)

No hardcoded secrets are used.

### 3) Add frontend service

- Create another service from the same repo
- Set **Root Directory** to `frontend`
- Railway will use:
  - `frontend/Dockerfile`
  - `frontend/railway.json`

Set frontend env var:

- `VITE_BACKEND_URL=https://<your-backend-service>.up.railway.app`

### 4) Verify

- Backend: `https://<backend>.up.railway.app/api/health`
- Frontend loads and shows broker state
- SAFE MODE should appear automatically if Upstox/feed is unavailable

## Also supported

- Render: `render.yaml`
- Vercel frontend: `frontend/vercel.json`
# Codex33
