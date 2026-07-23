"""Traffic telemetry ingest and smart-grid control decisions."""

import json

from fastapi import APIRouter, HTTPException

from app import control_engine
from app import repository as repo
from app.ml_anomaly import detect_traffic_anomaly
from app.schemas import HardwareTelemetry, SmartControlRequest, TwinTelemetry
from app.state import manager, smart_control_state
from app.utils import run_db

router = APIRouter()

# ─────────────────────────────────────────────
# REST ENDPOINTS - PORTED TRAFFIC SIMULATOR (y_prototype)
# ─────────────────────────────────────────────
@router.post("/api/telemetry")
async def receive_hardware_telemetry(data: HardwareTelemetry):
    control_decision = control_engine.decide(SmartControlRequest(
        district_id="nurzhol_sector_A",
        mode="AUTO",
        hardware={
            "temp_c": data.temp_c,
            "distance_cm": data.distance_cm,
            "flow_speed_kmh": data.flow_speed_kmh,
            "lane_blocked": data.lane_blocked,
            "power_kw": data.power_kw,
        }
    ))
    smart_control_state.update(control_decision)

    payload = {
        "source": "physical_hardware",
        "node_id": data.node_id,
        "type": "esp32_telemetry",
        "payload": {
            "temperature": data.temp_c,
            "distance_sensor": data.distance_cm,
            "calculated_speed": data.flow_speed_kmh,
            "lane_status": "BLOCKED" if data.lane_blocked else "CLEAR",
            "power_usage_kw": control_decision["power_usage_kw"],
            "control": control_decision,
        }
    }
    await manager.broadcast(payload)
    await manager.broadcast({
        "source": "smart_control",
        "type": "control_decision",
        "payload": control_decision,
    })
    return {"status": "SUCCESS"}

@router.post("/api/twin/telemetry")
async def receive_twin_telemetry(data: TwinTelemetry):
    m = data.metrics
    is_anomaly, anomaly_score, confidence = detect_traffic_anomaly(
        m.traffic_speed_kmh, m.congestion_index, m.air_quality_co2_ppm, m.facade_heat_loss_w_m2, m.ambient_temp_c
    )

    await run_db(repo.save_traffic_log, {
        "district_id":       data.district_id,
        "traffic_speed":     m.traffic_speed_kmh,
        "congestion_index":  m.congestion_index,
        "co2_ppm":           m.air_quality_co2_ppm,
        "heat_loss_wm2":     m.facade_heat_loss_w_m2,
        "ambient_temp_c":    m.ambient_temp_c,
        "is_anomaly":        int(is_anomaly),
        "anomaly_score":     round(anomaly_score, 4),
        "source":            "twin",
    })

    payload = {
        "source":      "twin_simulator",
        "type":        "twin_telemetry",
        "timestamp":   data.timestamp,
        "district_id": data.district_id,
        "metrics": {
            "traffic_speed_kmh":     m.traffic_speed_kmh,
            "congestion_index":      m.congestion_index,
            "air_quality_co2_ppm":   m.air_quality_co2_ppm,
            "facade_heat_loss_w_m2": m.facade_heat_loss_w_m2,
            "ambient_temp_c":        m.ambient_temp_c,
        },
        "ai_trigger":  data.ai_trigger,
        "ml_analysis": {
            "is_anomaly":     is_anomaly,
            "anomaly_score":  round(anomaly_score, 3),
            "confidence_pct": confidence,
        },
    }
    await manager.broadcast(payload)

    if data.ai_trigger or is_anomaly:
        control_decision = control_engine.decide(SmartControlRequest(
            district_id=data.district_id,
            mode="AUTO",
            metrics=m,
        ))
        smart_control_state.update(control_decision)
        await manager.broadcast({
            "source": "smart_control",
            "type": "control_decision",
            "payload": control_decision,
        })

    return {"status": "SUCCESS", "is_anomaly": is_anomaly}

# ─────────────────────────────────────────────
# SMART GRID TRAFFIC CONTROL OVERRIDES
# ─────────────────────────────────────────────
@router.get("/api/control/status")
async def get_control_status():
    return smart_control_state

@router.post("/api/control/decision")
async def create_control_decision(req: SmartControlRequest):
    decision = control_engine.decide(req)
    smart_control_state.update(decision)

    await run_db(repo.save_control_event, {
        "district_id": decision["district_id"],
        "mode": decision["mode"],
        "risk_level": decision["risk_level"],
        "signal_phase": decision["signal_phase"],
        "power_state": decision["power_state"],
        "power_usage_kw": decision["power_usage_kw"],
        "reason": decision["reason"],
        "action_json": json.dumps(decision["recommended_actions"]),
    })

    await manager.broadcast({
        "source": "smart_control",
        "type": "control_decision",
        "payload": decision,
    })
    return decision

@router.post("/api/control/manual")
async def manual_control(req: SmartControlRequest):
    if not req.manual_action:
        raise HTTPException(status_code=400, detail="manual_action is required")
    req.mode = "MANUAL"
    return await create_control_decision(req)
