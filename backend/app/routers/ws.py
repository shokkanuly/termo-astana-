"""WebSocket endpoints. Broadcasting itself lives in app.state.manager."""

import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.state import manager

logger = logging.getLogger("AstanaTwinCombinedAPI")

router = APIRouter()

# ─────────────────────────────────────────────
# WEBSOCKET CONNECTIONS (Supporting both /ws and /ws/telemetry)
# ─────────────────────────────────────────────
async def handle_websocket_connection(websocket: WebSocket, prefix_type: str = "init"):
    await manager.connect(websocket, prefix_type)
    try:
        await websocket.send_json({
            "type": "init",
            "data": {
                "nodes": list(manager.node_registry.values())
            }
        })
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            if msg.get("type") == "sensor_reading":
                reading = msg["data"]
                reading["timestamp"] = time.time()
                await manager.broadcast_telemetry(reading)
            elif msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
        logger.info(f"WS client disconnected — total: {len(manager)}")

@router.websocket("/ws")
async def websocket_ws(websocket: WebSocket):
    await handle_websocket_connection(websocket, "legacy")

@router.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await handle_websocket_connection(websocket, "telemetry")
