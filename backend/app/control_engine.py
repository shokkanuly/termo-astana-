"""Rule-based smart-grid control engine.

Maps a telemetry snapshot (or a manual operator override) onto a signal phase, relay
state and a recommended-action list. Used by the control routes and by the telemetry
ingest paths that auto-trigger a decision.
"""

from typing import Optional

from app.schemas import SmartControlRequest, TwinMetrics
from app.utils import utc_now


def estimate_power_kw(metrics: Optional[TwinMetrics], hardware: dict) -> float:
    if hardware.get("power_kw") is not None:
        return round(float(hardware["power_kw"]), 2)
    if not metrics:
        return 0.0
    heat_component = max(0.0, metrics.facade_heat_loss_w_m2 - 70.0) * 0.035
    co2_component = max(0.0, metrics.air_quality_co2_ppm - 400.0) * 0.002
    temp_component = max(0.0, metrics.ambient_temp_c - 25.0) * 0.18
    return round(2.8 + heat_component + co2_component + temp_component, 2)

def decide(req: SmartControlRequest) -> dict:
    metrics = req.metrics
    hardware = req.hardware or {}
    power_kw = estimate_power_kw(metrics, hardware)
    temp_c = float(hardware.get("temp_c") or hardware.get("temperature") or (metrics.ambient_temp_c if metrics else 0.0))
    speed = float(hardware.get("flow_speed_kmh") or (metrics.traffic_speed_kmh if metrics else 50.0))
    congestion = float(metrics.congestion_index if metrics else (100 if hardware.get("lane_blocked") else 20))
    heat_loss = float(metrics.facade_heat_loss_w_m2 if metrics else 90.0)
    lane_blocked = bool(hardware.get("lane_blocked", False))

    signal_phase = "GREEN_EW"
    power_state = "ON"
    relay_command = "RELAY_ON"
    risk = "LOW"
    actions = ["Keep normal monitoring cycle"]
    reason = "Telemetry is within normal operating range."

    if req.manual_action:
        action = req.manual_action.upper()
        if action == "POWER_OFF":
            power_state, relay_command = "OFF", "RELAY_OFF"
            risk, reason = "MANUAL", "Operator manually switched prototype power output off."
        elif action == "POWER_ON":
            power_state, relay_command = "ON", "RELAY_ON"
            risk, reason = "MANUAL", "Operator manually restored prototype power output."
        elif action in {"GREEN_EW", "GREEN_NS", "YELLOW_HOLD", "ALL_RED"}:
            signal_phase = action
            risk, reason = "MANUAL", f"Operator manually selected traffic phase {action}."
        actions = ["Manual override active", "Return to AUTO after demo step"]
    elif temp_c >= 45 or power_kw >= 9.5:
        risk = "CRITICAL"
        signal_phase = "ALL_RED"
        power_state = "OFF"
        relay_command = "RELAY_OFF"
        reason = "Critical heat or power load detected. Prototype relay output disabled."
        actions = ["Cut non-critical prototype load", "Hold traffic safely", "Notify operator"]
    elif lane_blocked or speed < 15:
        risk = "HIGH"
        signal_phase = "YELLOW_HOLD"
        power_state = "REDUCED" if power_kw > 6.5 else "ON"
        relay_command = "RELAY_LIMIT" if power_state == "REDUCED" else "RELAY_ON"
        reason = "Lane blockage detected. Holding cautious signal cycle and reducing load if needed."
        actions = ["Activate yellow caution", "Prioritize emergency clearance", "Watch power trend"]
    elif congestion >= 70 or speed < 28:
        risk = "MEDIUM"
        signal_phase = "GREEN_EW"
        power_state = "REDUCED" if power_kw > 7.0 or heat_loss > 145 else "ON"
        relay_command = "RELAY_LIMIT" if power_state == "REDUCED" else "RELAY_ON"
        reason = "Traffic congestion is high. Extending east-west green wave."
        actions = ["Extend green phase by 20 seconds", "Reduce non-critical lighting load", "Recheck in 30 seconds"]
    elif power_kw > 7.5 or temp_c >= 36:
        risk = "MEDIUM"
        signal_phase = "GREEN_NS"
        power_state = "REDUCED"
        relay_command = "RELAY_LIMIT"
        reason = "Power or temperature is rising. Reducing prototype load while keeping traffic moving."
        actions = ["Dim non-critical load", "Route flow through north-south phase", "Continue monitoring"]

    traffic_light = {
        "red": signal_phase == "ALL_RED",
        "yellow": signal_phase == "YELLOW_HOLD",
        "green": signal_phase in {"GREEN_EW", "GREEN_NS"},
    }

    return {
        "district_id": req.district_id,
        "mode": req.mode,
        "risk_level": risk,
        "signal_phase": signal_phase,
        "power_state": power_state,
        "relay_command": relay_command,
        "traffic_light": traffic_light,
        "power_usage_kw": power_kw,
        "reason": reason,
        "recommended_actions": actions,
        "last_updated": utc_now(),
    }
