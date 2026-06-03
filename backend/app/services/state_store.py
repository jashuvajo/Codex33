from __future__ import annotations

import json
from datetime import datetime
import asyncpg
import redis.asyncio as redis
from app.models.schemas import TelemetryFrame, TradeSignal


class StateStore:
    def __init__(self, redis_url: str, postgres_dsn: str) -> None:
        self._redis_url = redis_url
        self._postgres_dsn = postgres_dsn
        self.redis: redis.Redis | None = None
        self.pg_pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.redis = redis.from_url(self._redis_url, decode_responses=True)
        self.pg_pool = await asyncpg.create_pool(dsn=self._postgres_dsn, min_size=1, max_size=5)
        await self._init_tables()

    async def close(self) -> None:
        if self.redis:
            await self.redis.close()
        if self.pg_pool:
            await self.pg_pool.close()

    async def _init_tables(self) -> None:
        assert self.pg_pool is not None
        async with self.pg_pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry_journal (
                    id BIGSERIAL PRIMARY KEY,
                    ts TIMESTAMPTZ NOT NULL,
                    session TEXT NOT NULL,
                    payload JSONB NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trade_journal (
                    id BIGSERIAL PRIMARY KEY,
                    ts TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    payload JSONB NOT NULL
                );
                """
            )

    async def publish_telemetry(self, channel: str, frame: TelemetryFrame) -> None:
        if not self.redis:
            return
        await self.redis.publish(channel, frame.model_dump_json())

    async def store_telemetry(self, frame: TelemetryFrame) -> None:
        if not self.pg_pool:
            return
        payload = frame.model_dump(mode="json")
        async with self.pg_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO telemetry_journal (ts, session, payload) VALUES ($1, $2, $3::jsonb)",
                frame.timestamp,
                frame.session,
                json.dumps(payload),
            )

    async def store_trade_signal(self, signal: TradeSignal) -> None:
        if not self.pg_pool:
            return
        payload = signal.model_dump(mode="json")
        async with self.pg_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO trade_journal (ts, symbol, side, confidence, payload)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                signal.timestamp,
                signal.symbol,
                signal.side,
                signal.confidence,
                json.dumps(payload),
            )

    async def latest_journal_rows(self, limit: int = 100) -> list[dict]:
        if not self.pg_pool:
            return []
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ts, session, payload FROM telemetry_journal ORDER BY id DESC LIMIT $1",
                limit,
            )
            return [dict(row) for row in rows]

    async def latest_trade_rows(self, limit: int = 50) -> list[dict]:
        if not self.pg_pool:
            return []
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ts, symbol, side, confidence, payload FROM trade_journal ORDER BY id DESC LIMIT $1",
                limit,
            )
            return [dict(row) for row in rows]

    async def save_runtime_state(self, key: str, value: dict) -> None:
        if not self.redis:
            return
        await self.redis.set(f"runtime:{key}", json.dumps(value))

    async def get_runtime_state(self, key: str) -> dict | None:
        if not self.redis:
            return None
        raw = await self.redis.get(f"runtime:{key}")
        if not raw:
            return None
        return json.loads(raw)

    async def cache_timestamp(self, key: str, value: datetime) -> None:
        if not self.redis:
            return
        await self.redis.set(f"runtime:{key}", value.isoformat())
