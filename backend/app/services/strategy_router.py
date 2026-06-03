from __future__ import annotations

from datetime import datetime, timezone

from app.models.schemas import AiScore, MarketTick, RiskState, TradeSignal


class StrategyRouter:
    """
    Aggressive bullish scalping strategy focused on fast premium expansion.
    """

    def __init__(self, threshold: float) -> None:
        self.threshold = threshold

    def route(self, tick: MarketTick, ai_score: AiScore, risk: RiskState) -> TradeSignal | None:
        if not risk.allow_trading:
            return None
        if ai_score.trade_quality_score < self.threshold:
            return None
        if not (ai_score.bullish_momentum and ai_score.breakout_continuation):
            return None

        order_type = "IOC_LIMIT"
        if ai_score.trade_quality_score > self.threshold + 20 and ai_score.premium_expansion:
            order_type = "MARKET"

        quantity = max(risk.max_position_size, 1)
        return TradeSignal(
            symbol=tick.instrument_key,
            side="BUY",
            confidence=ai_score.trade_quality_score,
            order_type=order_type,
            quantity=quantity,
            entry_price=tick.ltp,
            timestamp=datetime.now(timezone.utc),
        )
