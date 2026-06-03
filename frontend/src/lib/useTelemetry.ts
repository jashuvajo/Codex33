import { useEffect, useMemo, useState } from "react";
import { backendWsUrl, fetchJson } from "./api";
import { TelemetryFrame } from "../types";

export function useTelemetry() {
  const [frame, setFrame] = useState<TelemetryFrame | null>(null);
  const [sessionAnalysis, setSessionAnalysis] = useState<Record<string, unknown> | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let cancelled = false;

    async function bootstrap() {
      try {
        const latest = await fetchJson<TelemetryFrame>("/api/telemetry/latest");
        if (!cancelled) {
          setFrame(latest);
        }
      } catch {
        // no-op: websocket can still provide first frame
      }

      try {
        const analysis = await fetchJson<Record<string, unknown>>("/api/analysis/session");
        if (!cancelled) {
          setSessionAnalysis(analysis);
        }
      } catch {
        // no-op
      }

      ws = new WebSocket(backendWsUrl("/api/ws/telemetry"));
      ws.onopen = () => {
        if (!cancelled) {
          setConnected(true);
          setError(null);
        }
      };
      ws.onclose = () => {
        if (!cancelled) {
          setConnected(false);
          setError("Telemetry socket disconnected");
        }
      };
      ws.onerror = () => {
        if (!cancelled) {
          setError("Telemetry socket error");
        }
      };
      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data) as TelemetryFrame;
          if (!cancelled) {
            setFrame(parsed);
          }
        } catch {
          // ignore malformed packets
        }
      };
    }

    bootstrap();
    const analysisTimer = setInterval(async () => {
      try {
        const analysis = await fetchJson<Record<string, unknown>>("/api/analysis/session");
        if (!cancelled) {
          setSessionAnalysis(analysis);
        }
      } catch {
        // ignore intermittent failures
      }
    }, 3000);

    return () => {
      cancelled = true;
      clearInterval(analysisTimer);
      if (ws) {
        ws.close();
      }
    };
  }, []);

  return useMemo(
    () => ({
      frame,
      sessionAnalysis,
      connected,
      error
    }),
    [frame, sessionAnalysis, connected, error]
  );
}
