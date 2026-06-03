from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models.schemas import BrokerHealth, PortfolioSnapshot, RiskState


@dataclass
class RiskConfig:
    daily_capital: float
    capital_allocation_pct: float
    max_exposure_pct: float
    max_drawdown_pct: float
    max_slippage_pct: float
    max_latency_ms: int


class RiskEngine:
    def __init__(self, config: RiskConfig) -> None:
        self.config = config
        self._cooldown_until: datetime | None = None
        self._peak_equity = config.daily_capital
        self._kill_switch = False

    def mark_kill_switch(self, enabled: bool) -> None:
        self._kill_switch = enabled

    def evaluate(
        self,
        broker: BrokerHealth,
        portfolio: PortfolioSnapshot,
        slippage_pct: float | None = None,
    ) -> RiskState:
        if self._kill_switch:
            return RiskState(safe_mode=True, allow_trading=False, kill_switch=True, reason="Kill switch active")

        if not broker.connected:
            return RiskState(safe_mode=True, allow_trading=False, reason="Broker disconnected")

        if broker.latency_ms and broker.latency_ms > self.config.max_latency_ms:
            return RiskState(safe_mode=True, allow_trading=False, reason="Latency protection triggered")

        if slippage_pct is not None and slippage_pct > self.config.max_slippage_pct:
            self._activate_cooldown(minutes=5)
            return RiskState(safe_mode=True, allow_trading=False, cooldown_active=True, reason="Slippage too high")

        if portfolio.exposure_pct is not None and portfolio.exposure_pct > self.config.max_exposure_pct:
            return RiskState(safe_mode=True, allow_trading=False, reason="Max exposure breached")

        equity = (portfolio.available_capital or self.config.daily_capital) + (portfolio.unrealized_pnl or 0.0)
        self._peak_equity = max(self._peak_equity, equity)
        drawdown_pct = 100.0 * max((self._peak_equity - equity), 0.0) / max(self._peak_equity, 1.0)
        if drawdown_pct > self.config.max_drawdown_pct:
            self._activate_cooldown(minutes=15)
            return RiskState(
                safe_mode=True,
                allow_trading=False,
                cooldown_active=True,
                reason="Drawdown protection triggered",
            )

        if self._cooldown_until and datetime.now(timezone.utc) < self._cooldown_until:
            return RiskState(
                safe_mode=True,
                allow_trading=False,
                cooldown_active=True,
                reason=f"Cooldown active until {self._cooldown_until.isoformat()}",
            )

        capital_alloc = (portfolio.available_capital or self.config.daily_capital) * (
            self.config.capital_allocation_pct / 100.0
        )
        max_position_size = int(max(capital_alloc, 0) // 1000)

        return RiskState(
            safe_mode=False,
            allow_trading=True,
            max_position_size=max(max_position_size, 1),
            reason="Risk checks passed",
        )

    def _activate_cooldown(self, minutes: int) -> None:
        self._cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
