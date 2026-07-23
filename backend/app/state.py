"""Shared runtime state for the API process.

Holds the live WebSocket connections and the most recent reading per node. This lives
outside ``main.py`` so background tasks — notably ``websocket_server.websocket_streamer``
— can broadcast without importing the app module, which would be an import cycle.
"""

import logging
from typing import Dict, List

from fastapi import WebSocket

from app.utils import utc_now

logger = logging.getLogger("AstanaTwinCombinedAPI")


class ConnectionManager:
    """Tracks connected WebSocket clients and the latest telemetry per node."""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []
        # Latest reading per node_id, replayed to each new client as the "init" frame.
        self.node_registry: Dict[str, dict] = {}

    def __len__(self) -> int:
        return len(self.active_connections)

    async def connect(self, websocket: WebSocket, prefix_type: str = "init") -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WS client connected ({prefix_type}) — total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, payload: dict) -> None:
        """Send to every client, dropping any that error out mid-send."""
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

    async def broadcast_telemetry(self, reading: dict) -> None:
        """Record a reading against its node, then push it to all clients."""
        self.node_registry[reading["node_id"]] = reading
        await self.broadcast({"type": "telemetry", "data": reading})


manager = ConnectionManager()

# Latest smart-grid control decision. Mutated in place via .update() by the control
# routes and by the telemetry ingest paths, and read back by GET /api/control/status.
smart_control_state = {
    "district_id": "nurzhol_sector_A",
    "mode": "AUTO",
    "risk_level": "LOW",
    "signal_phase": "GREEN_EW",
    "power_state": "ON",
    "relay_command": "RELAY_ON",
    "traffic_light": {"red": False, "yellow": False, "green": True},
    "power_usage_kw": 0.0,
    "reason": "System initialized. Waiting for telemetry.",
    "recommended_actions": ["Keep normal monitoring cycle"],
    "last_updated": utc_now(),
}
