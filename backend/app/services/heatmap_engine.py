from __future__ import annotations

from collections import defaultdict

from app.models.schemas import HeatmapMetrics, MarketTick


class HeatmapEngine:
    """
    Derives institutional-style heat zones from observed feed levels.
    This uses only live feed-derived price action and OI/volume hints.
    """

    def __init__(self) -> None:
        self._price_hits: dict[str, dict[int, int]] = defaultdict(dict)

    def update(self, tick: MarketTick) -> HeatmapMetrics:
        level = int(round(tick.ltp))
        bucket = self._price_hits[tick.instrument_key]
        bucket[level] = bucket.get(level, 0) + 1

        ranked = sorted(bucket.items(), key=lambda kv: kv[1], reverse=True)
        liquidity_walls = [float(price) for price, _ in ranked[:5]]
        stop_clusters = [float(price) for price, count in ranked if count > 8][:5]

        gamma_zones = []
        if tick.oi is not None:
            # OI-driven proxy zone near current level.
            gamma_shift = min(max(int(tick.oi // 100000), -100), 100)
            gamma_zones = [float(level + gamma_shift), float(level - gamma_shift)]

        sweep_zones = [float(level + 5), float(level - 5)]
        liquidity_voids = [float(price) for price, count in ranked if count == 1][:5]

        return HeatmapMetrics(
            liquidity_walls=liquidity_walls,
            gamma_zones=gamma_zones,
            sweep_zones=sweep_zones,
            liquidity_voids=liquidity_voids,
            stop_clusters=stop_clusters,
        )
