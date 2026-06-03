export type BrokerHealth = {
  connected: boolean;
  safe_mode: boolean;
  latency_ms: number | null;
  message: string;
  last_ok_at: string | null;
};

export type PortfolioSnapshot = {
  available_capital: number | null;
  used_margin: number | null;
  realized_pnl: number | null;
  unrealized_pnl: number | null;
  exposure_pct: number | null;
  active_positions: number;
  open_orders: number;
};

export type MarketTick = {
  instrument_key: string;
  ltp: number;
  volume: number | null;
  bid: number | null;
  ask: number | null;
  oi: number | null;
  timestamp: string;
};

export type OrderflowMetrics = {
  cumulative_delta: number;
  delta_velocity: number;
  dom_imbalance: number;
  aggressive_buyer_pressure: number;
  momentum_velocity: number;
  spread_quality: number;
  volume_spike_score: number;
};

export type HeatmapMetrics = {
  liquidity_walls: number[];
  gamma_zones: number[];
  sweep_zones: number[];
  liquidity_voids: number[];
  stop_clusters: number[];
};

export type AiScore = {
  trade_quality_score: number;
  bullish_momentum: boolean;
  breakout_continuation: boolean;
  premium_expansion: boolean;
  institutional_buying: boolean;
  reasons: string[];
};

export type RiskState = {
  safe_mode: boolean;
  allow_trading: boolean;
  max_position_size: number;
  cooldown_active: boolean;
  kill_switch: boolean;
  reason: string;
};

export type TradeSignal = {
  symbol: string;
  side: string;
  confidence: number;
  order_type: string;
  quantity: number;
  entry_price: number;
  timestamp: string;
};

export type TelemetryFrame = {
  timestamp: string;
  session: string;
  broker: BrokerHealth;
  portfolio: PortfolioSnapshot;
  orderflow: OrderflowMetrics;
  heatmap: HeatmapMetrics;
  ai: AiScore;
  risk: RiskState;
  latest_ticks: Record<string, MarketTick>;
  signal: TradeSignal | null;
};
