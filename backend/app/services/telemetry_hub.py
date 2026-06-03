from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.time_utils import get_market_session
from app.models.schemas import BrokerHealth, HeatmapMetrics, MarketTick, OrderflowMetrics, TelemetryFrame
from app.services.ai_engine import AiEngine
from app.services.analytics_engine import AnalyticsEngine
from app.services.execution_router import ExecutionRouter
from app.services.heatmap_engine import HeatmapEngine
from app.services.orderflow_engine import OrderflowEngine
from app.services.risk_engine import RiskEngine
from app.services.session_intelligence import SessionIntelligence
from app.services.state_store import StateStore
from app.services.strategy_router import StrategyRouter
from app.services.trailing_engine import TrailingEngine
from app.services.upstox_client import UpstoxClient

LOGGER = logging.getLogger(__name__)


class TelemetryHub:
    CHANNEL = "nexusquant.telemetry"

    def __init__(
        self,
        upstox_client: UpstoxClient,
        state_store: StateStore,
        ai_engine: AiEngine,
        risk_engine: RiskEngine,
        strategy_router: StrategyRouter,
        execution_router: ExecutionRouter,
        trailing_engine: TrailingEngine,
        analytics_engine: AnalyticsEngine,
        session_intelligence: SessionIntelligence,
        telemetry_interval_seconds: int,
        stale_feed_seconds: int,
    ) -> None:
        self.upstox = upstox_client
        self.state_store = state_store
        self.ai_engine = ai_engine
        self.risk_engine = risk_engine
        self.strategy_router = strategy_router
        self.execution_router = execution_router
        self.trailing_engine = trailing_engine
        self.analytics_engine = analytics_engine
        self.session_intelligence = session_intelligence
        self.telemetry_interval_seconds = telemetry_interval_seconds
        self.stale_feed_seconds = stale_feed_seconds
        self.orderflow_engine = OrderflowEngine()
        self.heatmap_engine = HeatmapEngine()
        self.latest_ticks: dict[str, MarketTick] = {}
        self.broker = BrokerHealth()
        self.last_frame: TelemetryFrame | None = None
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        self._tasks.append(asyncio.create_task(self.upstox.run_market_stream(self._on_tick, self._on_status)))
        self._tasks.append(asyncio.create_task(self._telemetry_loop()))
        LOGGER.info("Telemetry hub started")

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _on_tick(self, tick: MarketTick) -> None:
        self.latest_ticks[tick.instrument_key] = tick

    async def _on_status(self, status: BrokerHealth) -> None:
        self.broker = status

    async def _telemetry_loop(self) -> None:
        while True:
            try:
                profile_health = await self.upstox.profile_health()
                stream_alive = self._stream_is_fresh()
                streamer_ready = self.upstox.market_stream_connected and stream_alive
                broker_connected = profile_health.connected and streamer_ready

                self.broker = BrokerHealth(
                    connected=broker_connected,
                    safe_mode=not broker_connected,
                    latency_ms=profile_health.latency_ms,
                    message=(
                        f"{profile_health.message} ({self.upstox.streamer_mode})"
                        if broker_connected
                        else "SAFE MODE: waiting for successful live Upstox + MarketDataStreamerV3 feed"
                    ),
                    last_ok_at=profile_health.last_ok_at if broker_connected else None,
                )

                portfolio = await self.upstox.portfolio_snapshot() if profile_health.connected else self._empty_portfolio()
                latest_tick = self._pick_primary_tick()

                orderflow = OrderflowMetrics()
                heatmap = HeatmapMetrics()
                if latest_tick:
                    orderflow = self.orderflow_engine.update(latest_tick)
                    heatmap = self.heatmap_engine.update(latest_tick)

                ai_score = self.ai_engine.score(orderflow=orderflow, heatmap=heatmap)
                risk = self.risk_engine.evaluate(broker=self.broker, portfolio=portfolio)

                session = get_market_session()
                if session.name != "live":
                    risk.safe_mode = True
                    risk.allow_trading = False
                    risk.reason = f"{session.name.capitalize()} session: analysis-only mode"

                signal = None
                if latest_tick and risk.allow_trading:
                    signal = self.strategy_router.route(latest_tick, ai_score, risk)
                    if signal:
                        execution = await self.execution_router.execute(signal)
                        if execution.accepted:
                            self.trailing_engine.on_entry(signal.symbol, signal.entry_price)
                            await self.state_store.store_trade_signal(signal)
                        else:
                            self.risk_engine.mark_kill_switch(True)
                            risk.safe_mode = True
                            risk.allow_trading = False
                            risk.reason = execution.reason

                if latest_tick:
                    _ = self.trailing_engine.evaluate(
                        symbol=latest_tick.instrument_key,
                        ltp=latest_tick.ltp,
                        momentum_velocity=orderflow.momentum_velocity,
                    )

                session_note = self.session_intelligence.analyze(latest_tick, orderflow, ai_score)
                await self.state_store.save_runtime_state("session_intelligence", session_note)

                frame = TelemetryFrame(
                    timestamp=datetime.now(timezone.utc),
                    session=session.name,
                    broker=self.broker,
                    portfolio=portfolio,
                    orderflow=orderflow,
                    heatmap=heatmap,
                    ai=ai_score,
                    risk=risk,
                    latest_ticks=self.latest_ticks,
                    signal=signal,
                )
                self.last_frame = frame
                await self.state_store.publish_telemetry(self.CHANNEL, frame)
                await self.analytics_engine.persist(frame)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Telemetry loop failure: %s", exc)
            await asyncio.sleep(self.telemetry_interval_seconds)

    def _stream_is_fresh(self) -> bool:
        if not self.upstox.last_tick_at:
            return False
        return datetime.now(timezone.utc) - self.upstox.last_tick_at <= timedelta(seconds=self.stale_feed_seconds)

    def _pick_primary_tick(self) -> MarketTick | None:
        if not self.latest_ticks:
            return None
        for key in ("NSE_INDEX|Nifty 50", "BSE_INDEX|SENSEX"):
            if key in self.latest_ticks:
                return self.latest_ticks[key]
        return next(iter(self.latest_ticks.values()))

    def _empty_portfolio(self):
        from app.models.schemas import PortfolioSnapshot

        return PortfolioSnapshot()
