from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.state import get_app_state

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    state = get_app_state()
    frame = state.telemetry_hub.last_frame
    return {
        "ok": True,
        "broker_connected": frame.broker.connected if frame else False,
        "safe_mode": frame.risk.safe_mode if frame else True,
        "streamer_mode": state.upstox_client.streamer_mode,
        "sdk_marketdatastreamerv3_available": state.upstox_client.sdk_available,
    }


@router.get("/telemetry/latest")
async def latest_telemetry():
    state = get_app_state()
    frame = state.telemetry_hub.last_frame
    if not frame:
        raise HTTPException(status_code=503, detail="Telemetry not ready")
    return frame


@router.get("/analysis/session")
async def session_analysis():
    state = get_app_state()
    payload = await state.state_store.get_runtime_state("session_intelligence")
    return payload or {"message": "Session intelligence not available yet"}


@router.get("/analysis/closed-market")
async def closed_market_analysis():
    state = get_app_state()
    return await state.analytics_engine.closed_market_summary()


@router.get("/journal/trades")
async def trade_journal(limit: int = 50):
    state = get_app_state()
    return await state.state_store.latest_trade_rows(limit=limit)


@router.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket):
    await websocket.accept()
    state = get_app_state()
    pubsub = state.state_store.redis.pubsub() if state.state_store.redis else None
    if not pubsub:
        await websocket.send_json({"error": "Redis not connected"})
        await websocket.close()
        return

    await pubsub.subscribe(state.telemetry_hub.CHANNEL)
    try:
        if state.telemetry_hub.last_frame:
            await websocket.send_text(state.telemetry_hub.last_frame.model_dump_json())
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(state.telemetry_hub.CHANNEL)
        await pubsub.close()
