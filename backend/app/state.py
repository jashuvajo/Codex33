from __future__ import annotations

from dataclasses import dataclass

from app.services.analytics_engine import AnalyticsEngine
from app.services.telemetry_hub import TelemetryHub
from app.services.state_store import StateStore
from app.services.upstox_client import UpstoxClient


@dataclass
class AppState:
    upstox_client: UpstoxClient
    telemetry_hub: TelemetryHub
    state_store: StateStore
    analytics_engine: AnalyticsEngine


_APP_STATE: AppState | None = None


def set_app_state(state: AppState) -> None:
    global _APP_STATE
    _APP_STATE = state


def get_app_state() -> AppState:
    if _APP_STATE is None:
        raise RuntimeError("App state is not initialized")
    return _APP_STATE
