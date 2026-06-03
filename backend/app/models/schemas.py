from datetime import datetime
from pydantic import BaseModel, Field


class BrokerHealth(BaseModel):
    connected: bool = False
    safe_mode: bool = True
    latency_ms: float | None = None
    message: str = "Waiting for Upstox connection"
    last_ok_at: datetime | None = None


class PortfolioSnapshot(BaseModel):
    available_capital: float | None = None
    used_margin: float | None = None
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    exposure_pct: float | None = None
    active_positions: int = 0
    open_orders: int = 0


class MarketTick(BaseModel):
    instrument_key: str
    ltp: float
    volume: float | None = None
    bid: float | None = None
    ask: float | None = None
    oi: float | None = None
    timestamp: datetime


class OrderflowMetrics(BaseModel):
    cumulative_delta: float = 0.0
    delta_velocity: float = 0.0
    dom_imbalance: float = 0.0
    aggressive_buyer_pressure: float = 0.0
    momentum_velocity: float = 0.0
    spread_quality: float = 0.0
    volume_spike_score: float = 0.0


class HeatmapMetrics(BaseModel):
    liquidity_walls: list[float] = Field(default_factory=list)
    gamma_zones: list[float] = Field(default_factory=list)
    sweep_zones: list[float] = Field(default_factory=list)
    liquidity_voids: list[float] = Field(default_factory=list)
    stop_clusters: list[float] = Field(default_factory=list)


class AiScore(BaseModel):
    trade_quality_score: float = 0.0
    bullish_momentum: bool = False
    breakout_continuation: bool = False
    premium_expansion: bool = False
    institutional_buying: bool = False
    reasons: list[str] = Field(default_factory=list)


class RiskState(BaseModel):
    safe_mode: bool = True
    allow_trading: bool = False
    max_position_size: int = 0
    cooldown_active: bool = False
    kill_switch: bool = False
    reason: str = "SAFE MODE active"


class TradeSignal(BaseModel):
    symbol: str
    side: str
    confidence: float
    order_type: str
    quantity: int
    entry_price: float
    timestamp: datetime


class TelemetryFrame(BaseModel):
    timestamp: datetime
    session: str
    broker: BrokerHealth
    portfolio: PortfolioSnapshot
    orderflow: OrderflowMetrics
    heatmap: HeatmapMetrics
    ai: AiScore
    risk: RiskState
    latest_ticks: dict[str, MarketTick]
    signal: TradeSignal | None = None
