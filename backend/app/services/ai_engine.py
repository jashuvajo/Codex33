from __future__ import annotations

from app.models.schemas import AiScore, HeatmapMetrics, OrderflowMetrics


class AiEngine:
    def __init__(self, threshold: float) -> None:
        self.threshold = threshold

    def score(self, orderflow: OrderflowMetrics, heatmap: HeatmapMetrics, option_bias: float | None = None) -> AiScore:
        reasons: list[str] = []
        score = 0.0

        momentum_component = min(max(orderflow.momentum_velocity * 20.0, 0.0), 20.0)
        score += momentum_component
        if momentum_component > 8:
            reasons.append("Momentum velocity expansion")

        delta_component = min(max(orderflow.delta_velocity * 10.0, 0.0), 15.0)
        score += delta_component
        if delta_component > 6:
            reasons.append("Aggressive delta spike")

        spread_component = min(max(orderflow.spread_quality * 20.0, 0.0), 20.0)
        score += spread_component
        if spread_component > 10:
            reasons.append("Tight spread quality")

        volume_component = min(max(orderflow.volume_spike_score * 15.0, 0.0), 15.0)
        score += volume_component
        if volume_component > 6:
            reasons.append("Volume expansion")

        liquidity_component = 10.0 if len(heatmap.liquidity_walls) >= 2 else 0.0
        score += liquidity_component
        if liquidity_component:
            reasons.append("Liquidity wall confirmation")

        option_component = 0.0
        if option_bias is not None:
            option_component = min(max(option_bias * 20.0, -20.0), 20.0)
            score += max(option_component, 0.0)
            if option_component > 5:
                reasons.append("Option chain bullish bias")

        bullish_momentum = orderflow.momentum_velocity > 0 and orderflow.aggressive_buyer_pressure > 0
        breakout_continuation = orderflow.delta_velocity > 0 and orderflow.volume_spike_score > 0.5
        premium_expansion = orderflow.momentum_velocity > 0 and orderflow.volume_spike_score > 0.3
        institutional_buying = orderflow.dom_imbalance > 0.2 and len(heatmap.liquidity_walls) > 1

        return AiScore(
            trade_quality_score=round(score, 2),
            bullish_momentum=bullish_momentum,
            breakout_continuation=breakout_continuation,
            premium_expansion=premium_expansion,
            institutional_buying=institutional_buying,
            reasons=reasons,
        )
