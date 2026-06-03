from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.logger import configure_logging
from app.services.ai_engine import AiEngine
from app.services.analytics_engine import AnalyticsEngine
from app.services.execution_router import ExecutionRouter
from app.services.risk_engine import RiskConfig, RiskEngine
from app.services.session_intelligence import SessionIntelligence
from app.services.state_store import StateStore
from app.services.strategy_router import StrategyRouter
from app.services.telemetry_hub import TelemetryHub
from app.services.trailing_engine import TrailingEngine
from app.services.upstox_client import UpstoxClient
from app.state import AppState, get_app_state, set_app_state

settings = get_settings()
configure_logging(settings.log_level)
LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    state_store = StateStore(redis_url=settings.redis_url, postgres_dsn=settings.postgres_dsn)
    await state_store.connect()

    upstox_client = UpstoxClient(
        base_url=settings.upstox_base_url,
        access_token=settings.upstox_access_token,
        instrument_keys=settings.instrument_list,
        authorize_v3_path=settings.upstox_feed_authorize_v3_path,
        authorize_v2_path=settings.upstox_feed_authorize_v2_path,
    )

    ai_engine = AiEngine(threshold=settings.trade_quality_threshold)
    risk_engine = RiskEngine(
        RiskConfig(
            daily_capital=settings.daily_capital,
            capital_allocation_pct=settings.capital_allocation_pct,
            max_exposure_pct=settings.max_exposure_pct,
            max_drawdown_pct=settings.max_drawdown_pct,
            max_slippage_pct=settings.max_slippage_pct,
            max_latency_ms=settings.max_latency_ms,
        )
    )
    strategy_router = StrategyRouter(threshold=settings.trade_quality_threshold)
    execution_router = ExecutionRouter(upstox_client=upstox_client)
    trailing_engine = TrailingEngine()
    analytics_engine = AnalyticsEngine(state_store=state_store)
    session_intelligence = SessionIntelligence()
    telemetry_hub = TelemetryHub(
        upstox_client=upstox_client,
        state_store=state_store,
        ai_engine=ai_engine,
        risk_engine=risk_engine,
        strategy_router=strategy_router,
        execution_router=execution_router,
        trailing_engine=trailing_engine,
        analytics_engine=analytics_engine,
        session_intelligence=session_intelligence,
        telemetry_interval_seconds=settings.telemetry_interval_seconds,
        stale_feed_seconds=settings.stale_feed_seconds,
    )

    set_app_state(
        AppState(
            upstox_client=upstox_client,
            telemetry_hub=telemetry_hub,
            state_store=state_store,
            analytics_engine=analytics_engine,
        )
    )
    await telemetry_hub.start()
    LOGGER.info("NexusQuant backend initialized")
    try:
        yield
    finally:
        await telemetry_hub.stop()
        await upstox_client.close()
        await state_store.close()
        LOGGER.info("NexusQuant backend shutdown complete")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
async def root():
    state = get_app_state()
    frame = state.telemetry_hub.last_frame
    return {
        "service": settings.app_name,
        "status": "running",
        "broker_connected": frame.broker.connected if frame else False,
        "safe_mode": frame.risk.safe_mode if frame else True,
    }
