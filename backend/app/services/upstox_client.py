from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import importlib
import json
import logging
import time
from typing import Any

import httpx
import websockets

from app.models.schemas import BrokerHealth, MarketTick, PortfolioSnapshot

LOGGER = logging.getLogger(__name__)


TickHandler = Callable[[MarketTick], Awaitable[None]]
StatusHandler = Callable[[BrokerHealth], Awaitable[None]]


class UpstoxClient:
    """Thin client around Upstox REST + MarketDataStreamerV3 connectivity."""

    def __init__(
        self,
        base_url: str,
        access_token: str,
        instrument_keys: list[str],
        authorize_v3_path: str,
        authorize_v2_path: str,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.instrument_keys = instrument_keys
        self.authorize_v3_path = authorize_v3_path
        self.authorize_v2_path = authorize_v2_path
        self._http_client = httpx.AsyncClient(timeout=10.0)
        self._last_latency_ms: float | None = None
        self._market_stream_connected = False
        self._last_tick_at: datetime | None = None
        self._streamer_mode: str = "none"
        self._sdk_available = self._detect_streamer_v3_sdk()

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @property
    def market_stream_connected(self) -> bool:
        return self._market_stream_connected

    @property
    def last_tick_at(self) -> datetime | None:
        return self._last_tick_at

    @property
    def streamer_mode(self) -> str:
        return self._streamer_mode

    @property
    def sdk_available(self) -> bool:
        return self._sdk_available

    async def close(self) -> None:
        await self._http_client.aclose()

    def _detect_streamer_v3_sdk(self) -> bool:
        try:
            module = importlib.import_module("upstox_client")
            return hasattr(module, "MarketDataStreamerV3")
        except Exception:
            return False

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        start = time.perf_counter()
        response = await self._http_client.request(method, url, headers=self.headers, json=payload)
        self._last_latency_ms = (time.perf_counter() - start) * 1000.0
        response.raise_for_status()
        return response.json()

    async def profile_health(self) -> BrokerHealth:
        if not self.access_token:
            return BrokerHealth(
                connected=False,
                safe_mode=True,
                message="UPSTOX_ACCESS_TOKEN missing",
            )
        try:
            await self._request("GET", "/user/profile")
            return BrokerHealth(
                connected=True,
                safe_mode=False,
                latency_ms=self._last_latency_ms,
                message=(
                    "Connected to Upstox + MarketDataStreamerV3"
                    if self._market_stream_connected
                    else "Connected to Upstox REST, waiting for MarketDataStreamerV3 ticks"
                ),
                last_ok_at=datetime.now(timezone.utc),
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Profile health failed: %s", exc)
            return BrokerHealth(
                connected=False,
                safe_mode=True,
                latency_ms=self._last_latency_ms,
                message=f"Upstox profile check failed: {exc}",
            )

    async def portfolio_snapshot(self) -> PortfolioSnapshot:
        funds = await self._safe_get("/user/get-funds-and-margin")
        positions = await self._safe_get("/portfolio/short-term-positions")
        orders = await self._safe_get("/order/retrieve-all")

        available_capital = _extract_number(funds, ("data", "equity", "available_margin"))
        used_margin = _extract_number(funds, ("data", "equity", "used_margin"))
        realized_pnl = _extract_number(funds, ("data", "equity", "realized_m2m"))
        unrealized_pnl = _extract_number(funds, ("data", "equity", "unrealized_m2m"))

        positions_list = _extract_list(positions, ("data",))
        orders_list = _extract_list(orders, ("data",))
        active_positions = len([p for p in positions_list if float(p.get("quantity", 0)) != 0])
        open_orders = len([o for o in orders_list if o.get("status", "").upper() in {"OPEN", "TRIGGER_PENDING"}])
        exposure_pct = None
        if available_capital and used_margin is not None and available_capital > 0:
            exposure_pct = (used_margin / available_capital) * 100.0

        return PortfolioSnapshot(
            available_capital=available_capital,
            used_margin=used_margin,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            exposure_pct=exposure_pct,
            active_positions=active_positions,
            open_orders=open_orders,
        )

    async def _safe_get(self, path: str) -> dict[str, Any]:
        try:
            return await self._request("GET", path)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Upstox GET %s failed: %s", path, exc)
            return {}

    async def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/order/place", payload)

    async def fetch_option_chain(self, instrument_key: str, expiry_date: str) -> dict[str, Any]:
        # Upstox option chain endpoint for live contract snapshots.
        path = f"/option/chain?instrument_key={instrument_key}&expiry_date={expiry_date}"
        return await self._request("GET", path)

    async def market_authorize_url(self) -> str:
        try:
            resp = await self._request("GET", self.authorize_v3_path)
            return _extract_str(resp, ("data", "authorized_redirect_uri"))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("V3 authorize failed (%s), trying V2 path", exc)
            resp = await self._request("GET", self.authorize_v2_path)
            return _extract_str(resp, ("data", "authorized_redirect_uri"))

    async def run_market_stream(self, on_tick: TickHandler, on_status: StatusHandler) -> None:
        """Keeps reconnecting; emits connected=false on failures."""
        if self._sdk_available:
            try:
                await self._run_market_streamer_v3_sdk(on_tick, on_status)
                return
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("SDK streamer V3 path failed: %s", exc)

        # Fallback: direct v3 authorized websocket flow (still real Upstox feed).
        await self._run_market_stream_raw_ws(on_tick, on_status)

    async def _run_market_streamer_v3_sdk(self, on_tick: TickHandler, on_status: StatusHandler) -> None:
        module = importlib.import_module("upstox_client")
        configuration_cls = getattr(module, "Configuration")
        api_client_cls = getattr(module, "ApiClient")
        streamer_cls = getattr(module, "MarketDataStreamerV3")

        config = configuration_cls()
        config.access_token = self.access_token
        client = api_client_cls(config)
        streamer = streamer_cls(client, self.instrument_keys, "full")

        connected_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        async def _emit_connected(connected: bool, message: str) -> None:
            self._market_stream_connected = connected
            if connected:
                self._streamer_mode = "sdk_v3"
            await on_status(
                BrokerHealth(
                    connected=connected,
                    safe_mode=not connected,
                    latency_ms=self._last_latency_ms,
                    message=message,
                    last_ok_at=datetime.now(timezone.utc) if connected else None,
                )
            )

        def _on_open() -> None:
            connected_event.set()
            loop.create_task(_emit_connected(True, "MarketDataStreamerV3 connected"))

        def _on_close() -> None:
            loop.create_task(_emit_connected(False, "MarketDataStreamerV3 disconnected"))

        def _on_error(error: Any) -> None:
            loop.create_task(_emit_connected(False, f"MarketDataStreamerV3 error: {error}"))

        def _on_message(message: Any) -> None:
            tick = _parse_tick_message(message)
            if tick:
                self._last_tick_at = tick.timestamp
                loop.create_task(on_tick(tick))

        streamer.on("open", _on_open)
        streamer.on("close", _on_close)
        streamer.on("error", _on_error)
        streamer.on("message", _on_message)
        streamer.connect()

        await connected_event.wait()
        while True:
            await asyncio.sleep(1)

    async def _run_market_stream_raw_ws(self, on_tick: TickHandler, on_status: StatusHandler) -> None:
        reconnect_delay = 2
        while True:
            try:
                ws_url = await self.market_authorize_url()
                async with websockets.connect(ws_url, max_size=2_000_000, ping_interval=10) as ws:
                    self._market_stream_connected = True
                    self._streamer_mode = "raw_v3_ws"
                    await on_status(
                        BrokerHealth(
                            connected=True,
                            safe_mode=False,
                            latency_ms=self._last_latency_ms,
                            message="Upstox market feed connected (raw v3 websocket)",
                            last_ok_at=datetime.now(timezone.utc),
                        )
                    )

                    subscribe_payload = {
                        "guid": "nexusquant",
                        "method": "sub",
                        "data": {"mode": "full", "instrumentKeys": self.instrument_keys},
                    }
                    await ws.send(json.dumps(subscribe_payload))

                    async for message in ws:
                        tick = _parse_tick_message(message)
                        if tick:
                            self._last_tick_at = tick.timestamp
                            await on_tick(tick)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Raw WS stream failed; reconnecting: %s", exc)
                self._market_stream_connected = False
                await on_status(
                    BrokerHealth(
                        connected=False,
                        safe_mode=True,
                        latency_ms=self._last_latency_ms,
                        message=f"Market feed disconnected: {exc}",
                    )
                )
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 30)


def _parse_tick_message(raw: Any) -> MarketTick | None:
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
    elif isinstance(raw, dict):
        payload = raw
    else:
        return None

    data = payload.get("data") or payload
    feeds = data.get("feeds") if isinstance(data, dict) else None
    if isinstance(feeds, dict):
        for instrument_key, packet in feeds.items():
            full_feed = packet.get("fullFeed") or packet.get("ff") or packet
            market_ff = full_feed.get("marketFF") if isinstance(full_feed, dict) else None
            ltpc = (market_ff or full_feed or {}).get("ltpc", {})
            if not ltpc:
                continue
            ltp = ltpc.get("ltp")
            if ltp is None:
                continue
            bid_ask = (market_ff or {}).get("marketLevel", {}).get("bidAskQuote", [])
            bid = bid_ask[0].get("bp") if bid_ask else None
            ask = bid_ask[0].get("ap") if bid_ask else None
            return MarketTick(
                instrument_key=instrument_key,
                ltp=float(ltp),
                volume=_safe_float((market_ff or {}).get("vtt")),
                bid=_safe_float(bid),
                ask=_safe_float(ask),
                oi=_safe_float((full_feed or {}).get("oi")),
                timestamp=datetime.now(timezone.utc),
            )

    instrument_key = payload.get("instrument_key") or payload.get("symbol")
    ltp = payload.get("ltp")
    if instrument_key and ltp is not None:
        return MarketTick(
            instrument_key=instrument_key,
            ltp=float(ltp),
            volume=_safe_float(payload.get("volume")),
            bid=_safe_float(payload.get("bid")),
            ask=_safe_float(payload.get("ask")),
            oi=_safe_float(payload.get("oi")),
            timestamp=datetime.now(timezone.utc),
        )
    return None


def _extract_number(data: dict[str, Any], path: tuple[str, ...]) -> float | None:
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_str(data: dict[str, Any], path: tuple[str, ...]) -> str:
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            raise KeyError(path)
        value = value.get(key)
    if not value or not isinstance(value, str):
        raise ValueError(f"Missing string at path {path}")
    return value


def _extract_list(data: dict[str, Any], path: tuple[str, ...]) -> list[dict[str, Any]]:
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return []
        value = value.get(key)
    return value if isinstance(value, list) else []


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
