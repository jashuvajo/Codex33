from __future__ import annotations

from datetime import datetime
from statistics import mean

from app.models.schemas import TelemetryFrame
from app.services.state_store import StateStore


class AnalyticsEngine:
    def __init__(self, state_store: StateStore) -> None:
        self.state_store = state_store

    async def persist(self, frame: TelemetryFrame) -> None:
        await self.state_store.store_telemetry(frame)

    async def closed_market_summary(self) -> dict:
        rows = await self.state_store.latest_journal_rows(limit=500)
        if not rows:
            return {"message": "No telemetry journal data available yet."}

        tq_scores: list[float] = []
        bullish_count = 0
        for row in rows:
            payload = row.get("payload", {})
            ai = payload.get("ai", {})
            score = ai.get("trade_quality_score")
            if score is not None:
                tq_scores.append(float(score))
            if ai.get("bullish_momentum"):
                bullish_count += 1

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "samples": len(rows),
            "avg_tqs": round(mean(tq_scores), 2) if tq_scores else None,
            "bullish_frames": bullish_count,
            "bullish_ratio_pct": round((bullish_count / len(rows)) * 100.0, 2),
        }
