from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime

from app.models.schemas import MarketTick, OrderflowMetrics


@dataclass
class TickDelta:
    ts: datetime
    price_delta: float
    volume_delta: float
    spread: float | None


class OrderflowEngine:
    def __init__(self) -> None:
        self._last_tick: dict[str, MarketTick] = {}
        self._deltas: dict[str, deque[TickDelta]] = defaultdict(lambda: deque(maxlen=180))
        self._cumulative_delta = 0.0

    def update(self, tick: MarketTick) -> OrderflowMetrics:
        prev = self._last_tick.get(tick.instrument_key)
        if prev is None:
            self._last_tick[tick.instrument_key] = tick
            return OrderflowMetrics()

        price_delta = tick.ltp - prev.ltp
        volume_delta = max((tick.volume or 0.0) - (prev.volume or 0.0), 0.0)
        spread = None
        if tick.bid and tick.ask and tick.ask > 0:
            spread = abs(tick.ask - tick.bid)

        self._deltas[tick.instrument_key].append(
            TickDelta(ts=tick.timestamp, price_delta=price_delta, volume_delta=volume_delta, spread=spread)
        )
        self._last_tick[tick.instrument_key] = tick

        window = self._deltas[tick.instrument_key]
        total_volume = sum(row.volume_delta for row in window)
        total_price_delta = sum(row.price_delta for row in window)
        positive_ticks = sum(1 for row in window if row.price_delta > 0)
        negative_ticks = sum(1 for row in window if row.price_delta < 0)
        avg_spread = _avg([row.spread for row in window if row.spread is not None])
        max_volume = max((row.volume_delta for row in window), default=0.0)
        latest_volume = window[-1].volume_delta if window else 0.0
        volume_spike_score = latest_volume / max_volume if max_volume > 0 else 0.0

        self._cumulative_delta += total_price_delta * max(total_volume, 1.0)

        dom_imbalance = 0.0
        total_ticks = positive_ticks + negative_ticks
        if total_ticks > 0:
            dom_imbalance = (positive_ticks - negative_ticks) / total_ticks

        momentum_velocity = total_price_delta / max(len(window), 1)
        aggressive_buyer_pressure = max(dom_imbalance, 0.0) * max(momentum_velocity, 0.0)
        spread_quality = 0.0 if avg_spread is None else max(0.0, 1.0 - (avg_spread / max(tick.ltp, 1.0)))

        return OrderflowMetrics(
            cumulative_delta=self._cumulative_delta,
            delta_velocity=total_price_delta,
            dom_imbalance=dom_imbalance,
            aggressive_buyer_pressure=aggressive_buyer_pressure,
            momentum_velocity=momentum_velocity,
            spread_quality=spread_quality,
            volume_spike_score=volume_spike_score,
        )


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)
