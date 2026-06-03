import { useMemo } from "react";
import { useTelemetry } from "./lib/useTelemetry";
import { MarketTick, TelemetryFrame } from "./types";

function Metric({
  label,
  value,
  danger = false,
  positive = false
}: {
  label: string;
  value: string;
  danger?: boolean;
  positive?: boolean;
}) {
  const valueClass = danger
    ? "text-terminal-negative"
    : positive
      ? "text-terminal-positive"
      : "text-terminal-text";
  return (
    <div className="rounded border border-terminal-border p-2">
      <div className="text-[10px] uppercase tracking-wider text-slate-400">{label}</div>
      <div className={`text-sm font-semibold ${valueClass}`}>{value}</div>
    </div>
  );
}

function numberOrNA(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return value.toFixed(digits);
}

function TickTable({ ticks }: { ticks: Record<string, MarketTick> }) {
  const entries = Object.values(ticks);
  return (
    <div className="terminal-panel">
      <div className="terminal-title">Execution HUD</div>
      {entries.length === 0 ? (
        <div className="text-sm text-slate-400">Waiting for live tick stream from Upstox.</div>
      ) : (
        <div className="space-y-2">
          {entries.map((tick) => (
            <div
              key={tick.instrument_key}
              className="grid grid-cols-6 gap-2 rounded border border-terminal-border p-2 text-xs"
            >
              <div className="col-span-2 font-semibold">{tick.instrument_key}</div>
              <div>LTP: {numberOrNA(tick.ltp)}</div>
              <div>Bid: {numberOrNA(tick.bid)}</div>
              <div>Ask: {numberOrNA(tick.ask)}</div>
              <div>Vol: {numberOrNA(tick.volume, 0)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function BrokerBanner({ frame, wsConnected }: { frame: TelemetryFrame | null; wsConnected: boolean }) {
  const disconnected = !frame?.broker.connected;
  const safeMode = frame?.risk.safe_mode ?? true;
  return (
    <div
      className={`rounded-lg border p-3 ${
        disconnected || safeMode
          ? "border-terminal-negative bg-red-950/30"
          : "border-terminal-positive bg-emerald-950/20"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-slate-300">Broker Health</div>
          <div className="text-sm font-semibold">
            {disconnected ? "DISCONNECTED / SAFE MODE" : "CONNECTED / LIVE FEED VERIFIED"}
          </div>
          <div className="text-xs text-slate-300">{frame?.broker.message ?? "Waiting for telemetry..."}</div>
        </div>
        <div className="flex gap-2 text-xs">
          <span className={`rounded px-2 py-1 ${wsConnected ? "bg-emerald-700/40" : "bg-red-700/40"}`}>
            WS {wsConnected ? "UP" : "DOWN"}
          </span>
          <span className="rounded bg-slate-700/60 px-2 py-1">
            Latency: {numberOrNA(frame?.broker.latency_ms)} ms
          </span>
        </div>
      </div>
    </div>
  );
}

function App() {
  const { frame, sessionAnalysis, connected, error } = useTelemetry();
  const ticks = frame?.latest_ticks ?? {};

  const pnlPositive = (frame?.portfolio.unrealized_pnl ?? 0) >= 0;
  const reasons = useMemo(() => frame?.ai.reasons.join(" | ") || "No high-confidence setup", [frame?.ai.reasons]);

  return (
    <div className="min-h-screen bg-terminal-bg p-4 text-terminal-text">
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-terminal-accent">NexusQuant</h1>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">
            Minimal Institutional AI Scalping Terminal (NIFTY + SENSEX)
          </div>
        </div>
        <div className="rounded border border-terminal-border px-3 py-2 text-xs">
          Session: <span className="font-semibold uppercase">{frame?.session ?? "unknown"}</span>
        </div>
      </header>

      <BrokerBanner frame={frame} wsConnected={connected} />
      {error ? <div className="mt-2 text-xs text-terminal-warning">{error}</div> : null}

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <TickTable ticks={ticks} />

        <div className="terminal-panel">
          <div className="terminal-title">Upstox Portfolio</div>
          <div className="grid grid-cols-2 gap-2">
            <Metric label="Available Capital" value={numberOrNA(frame?.portfolio.available_capital)} />
            <Metric label="Used Margin" value={numberOrNA(frame?.portfolio.used_margin)} />
            <Metric label="Realized PnL" value={numberOrNA(frame?.portfolio.realized_pnl)} />
            <Metric
              label="Unrealized PnL"
              value={numberOrNA(frame?.portfolio.unrealized_pnl)}
              positive={pnlPositive}
              danger={!pnlPositive}
            />
            <Metric label="Exposure %" value={numberOrNA(frame?.portfolio.exposure_pct)} />
            <Metric label="Open Orders" value={String(frame?.portfolio.open_orders ?? 0)} />
          </div>
        </div>

        <div className="terminal-panel">
          <div className="terminal-title">Risk Engine</div>
          <div className="space-y-2 text-sm">
            <div>
              SAFE MODE:{" "}
              <span className={frame?.risk.safe_mode ? "text-terminal-warning font-semibold" : "text-terminal-positive"}>
                {String(frame?.risk.safe_mode ?? true)}
              </span>
            </div>
            <div>Allow Trading: {String(frame?.risk.allow_trading ?? false)}</div>
            <div>Max Position Size: {frame?.risk.max_position_size ?? 0}</div>
            <div>Cooldown: {String(frame?.risk.cooldown_active ?? false)}</div>
            <div>Reason: {frame?.risk.reason ?? "N/A"}</div>
          </div>
        </div>

        <div className="terminal-panel">
          <div className="terminal-title">Orderflow Analytics</div>
          <div className="grid grid-cols-2 gap-2">
            <Metric label="Cumulative Delta" value={numberOrNA(frame?.orderflow.cumulative_delta)} />
            <Metric label="Delta Velocity" value={numberOrNA(frame?.orderflow.delta_velocity)} />
            <Metric label="DOM Imbalance" value={numberOrNA(frame?.orderflow.dom_imbalance)} />
            <Metric label="Aggressive Buyers" value={numberOrNA(frame?.orderflow.aggressive_buyer_pressure)} />
            <Metric label="Momentum Velocity" value={numberOrNA(frame?.orderflow.momentum_velocity)} />
            <Metric label="Spread Quality" value={numberOrNA(frame?.orderflow.spread_quality)} />
          </div>
        </div>

        <div className="terminal-panel">
          <div className="terminal-title">Heatmap Terminal</div>
          <div className="space-y-2 text-sm">
            <div>Liquidity Walls: {(frame?.heatmap.liquidity_walls ?? []).join(", ") || "N/A"}</div>
            <div>Stop Clusters: {(frame?.heatmap.stop_clusters ?? []).join(", ") || "N/A"}</div>
            <div>Gamma Zones: {(frame?.heatmap.gamma_zones ?? []).join(", ") || "N/A"}</div>
            <div>Sweep Zones: {(frame?.heatmap.sweep_zones ?? []).join(", ") || "N/A"}</div>
            <div>Liquidity Voids: {(frame?.heatmap.liquidity_voids ?? []).join(", ") || "N/A"}</div>
          </div>
        </div>

        <div className="terminal-panel">
          <div className="terminal-title">AI Matrix</div>
          <div className="space-y-2 text-sm">
            <div className="text-2xl font-bold text-terminal-accent">
              TQS: {numberOrNA(frame?.ai.trade_quality_score)}
            </div>
            <div>Bullish Momentum: {String(frame?.ai.bullish_momentum ?? false)}</div>
            <div>Breakout Continuation: {String(frame?.ai.breakout_continuation ?? false)}</div>
            <div>Premium Expansion: {String(frame?.ai.premium_expansion ?? false)}</div>
            <div>Institutional Buying: {String(frame?.ai.institutional_buying ?? false)}</div>
            <div className="text-xs text-slate-400">{reasons}</div>
          </div>
        </div>

        <div className="terminal-panel">
          <div className="terminal-title">Session Intelligence</div>
          <pre className="overflow-auto whitespace-pre-wrap text-xs text-slate-300">
            {JSON.stringify(sessionAnalysis ?? { message: "Waiting..." }, null, 2)}
          </pre>
        </div>

        <div className="terminal-panel">
          <div className="terminal-title">Trade Journal</div>
          {frame?.signal ? (
            <div className="text-sm">
              <div>
                {frame.signal.side} {frame.signal.symbol}
              </div>
              <div>Type: {frame.signal.order_type}</div>
              <div>Qty: {frame.signal.quantity}</div>
              <div>Entry: {numberOrNA(frame.signal.entry_price)}</div>
              <div>Confidence: {numberOrNA(frame.signal.confidence)}</div>
            </div>
          ) : (
            <div className="text-sm text-slate-400">No active AI signal in current frame.</div>
          )}
        </div>

        <div className="terminal-panel">
          <div className="terminal-title">Settings</div>
          <div className="space-y-1 text-xs text-slate-300">
            <div>Mode progression: Simulator → Paper → Live</div>
            <div>Live trading locked unless broker + feed are both healthy.</div>
            <div>Instrument scope: NIFTY, SENSEX only.</div>
            <div>Deploy: Frontend on Vercel, backend on Render/AWS Mumbai.</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
