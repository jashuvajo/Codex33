from __future__ import annotations

from app.core.time_utils import get_market_session
from app.models.schemas import AiScore, MarketTick, OrderflowMetrics


class SessionIntelligence:
    def analyze(self, latest_tick: MarketTick | None, orderflow: OrderflowMetrics, ai: AiScore) -> dict:
        session = get_market_session()
        if session.name == "premarket":
            return self._premarket_analysis(latest_tick, orderflow, ai)
        if session.name == "live":
            return self._live_analysis(latest_tick, orderflow, ai)
        return self._closed_market_analysis(latest_tick, orderflow, ai)

    def _premarket_analysis(self, tick: MarketTick | None, orderflow: OrderflowMetrics, ai: AiScore) -> dict:
        return {
            "mode": "premarket",
            "message": "Indian premarket buildup analysis active.",
            "ltp": tick.ltp if tick else None,
            "momentum_probe": orderflow.momentum_velocity,
            "watch_for_open_drive": ai.trade_quality_score >= 50,
        }

    def _live_analysis(self, tick: MarketTick | None, orderflow: OrderflowMetrics, ai: AiScore) -> dict:
        return {
            "mode": "live",
            "message": "Live market scalping intelligence active.",
            "ltp": tick.ltp if tick else None,
            "breakout_risk": "high" if orderflow.volume_spike_score > 0.7 else "normal",
            "aggressive_bullish_setup": ai.bullish_momentum and ai.breakout_continuation,
        }

    def _closed_market_analysis(self, tick: MarketTick | None, orderflow: OrderflowMetrics, ai: AiScore) -> dict:
        return {
            "mode": "closed",
            "message": "Closed market review mode active; live trading disabled.",
            "last_ltp": tick.ltp if tick else None,
            "last_momentum_velocity": orderflow.momentum_velocity,
            "next_session_bias": "bullish" if ai.trade_quality_score > 60 else "neutral",
        }
