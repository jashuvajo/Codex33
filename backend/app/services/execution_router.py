from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.models.schemas import TradeSignal
from app.services.upstox_client import UpstoxClient

LOGGER = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    accepted: bool
    order_id: str | None
    execution_latency_ms: float
    slippage_pct: float | None
    raw: dict[str, Any]
    reason: str


class ExecutionRouter:
    def __init__(self, upstox_client: UpstoxClient) -> None:
        self.upstox_client = upstox_client

    async def execute(self, signal: TradeSignal) -> ExecutionResult:
        start = time.perf_counter()
        payload = {
            "quantity": signal.quantity,
            "product": "I",
            "validity": "DAY",
            "price": signal.entry_price if signal.order_type == "IOC_LIMIT" else 0,
            "tag": "nexusquant",
            "instrument_token": signal.symbol,
            "order_type": "LIMIT" if signal.order_type == "IOC_LIMIT" else "MARKET",
            "transaction_type": signal.side,
            "disclosed_quantity": 0,
            "trigger_price": 0,
            "is_amo": False,
        }
        if signal.order_type == "IOC_LIMIT":
            payload["validity"] = "IOC"

        try:
            response = await self.upstox_client.place_order(payload)
            latency_ms = (time.perf_counter() - start) * 1000.0
            order_id = (
                response.get("data", {}).get("order_id")
                or response.get("data", {}).get("orderId")
                or response.get("order_id")
            )
            return ExecutionResult(
                accepted=bool(order_id),
                order_id=order_id,
                execution_latency_ms=latency_ms,
                slippage_pct=None,
                raw=response,
                reason="Order sent to Upstox",
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = (time.perf_counter() - start) * 1000.0
            LOGGER.warning("Order execution failed: %s", exc)
            return ExecutionResult(
                accepted=False,
                order_id=None,
                execution_latency_ms=latency_ms,
                slippage_pct=None,
                raw={},
                reason=f"Execution failed: {exc}",
            )
