import os
import json
import time
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
from pathlib import Path
from functools import partial

import httpx
import pandas as pd
import numpy as np

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.database import get_db, init_db, DB_BACKEND
from app.osm_ingest import ingest_data
from app.weather import get_astana_weather
from app.ml_anomaly import detect_anomaly, detect_traffic_anomaly
from app.weather_worker import weather_polling_worker
from app.websocket_server import websocket_streamer, severity_from_w

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
logger = logging.getLogger("AstanaTwinCombinedAPI")

# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS (Consolidated from all projects)
# ─────────────────────────────────────────────
class HardwareTelemetry(BaseModel):
    node_id: str
    temp_c: float
    distance_cm: float
    flow_speed_kmh: float
    lane_blocked: bool
    power_kw: float

class TwinMetrics(BaseModel):
    traffic_speed_kmh: float
    congestion_index: float
    air_quality_co2_ppm: float
    facade_heat_loss_w_m2: float
    ambient_temp_c: float

class TwinTelemetry(BaseModel):
    timestamp: str
    district_id: str
    metrics: TwinMetrics
    ai_trigger: bool

class TelemetryPayload(BaseModel):
    city: str
    district_id: str
    metrics: TwinMetrics

class ThermoPayload(BaseModel):
    building_id: str
    name: str
    age: int
    current_loss_wm2: float
    insulation_type: str
    target_thickness_mm: int
    calculated_reduction_percent: int

class ChatRequest(BaseModel):
    message: str
    mode: str                          # 'traffic' | 'thermo'
    session_id: str = "default"
    context: dict = {}

class SmartControlRequest(BaseModel):
    district_id: str = "nurzhol_sector_A"
    mode: str = "AUTO"
    metrics: Optional[TwinMetrics] = None
    hardware: dict = {}
    manual_action: Optional[str] = None

class ESP32Payload(BaseModel):
    node_id: str
    t_in: float
    t_out: float
    window_open: bool
    humidity: Optional[float] = None

# ─────────────────────────────────────────────
# FASTAPI LIFESPAN
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global DB_BACKEND
    # 1. Initialize tables (PostgreSQL or SQLite fallback)
    init_db()
    import app.database as db_mod
    DB_BACKEND = db_mod.DB_BACKEND
    
    # 2. Automatically ingest OSM buildings if empty
    try:
        count = 0
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM buildings;")
            count = cur.fetchone()[0]
                
        if count <= 1:
            print("Buildings database is empty. Running OpenStreetMap ingestion...")
            ingest_data()
        else:
            print(f"Database contains {count} buildings. Skipping ingestion.")
    except Exception as e:
        print(f"Failed to check/ingest buildings: {e}")
        
    # 3. Start background simulation workers
    asyncio.create_task(weather_polling_worker())
    asyncio.create_task(websocket_streamer())
        
    yield

# ─────────────────────────────────────────────
# APP DEFINITION
# ─────────────────────────────────────────────
app = FastAPI(
    title="Astana Twin Unified API", 
    version="4.0", 
    description="Combined Digital Thermal Twin & Traffic Management platform for Astana, Kazakhstan",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections & registry
WS_CLIENTS: List[WebSocket] = []
NODE_REGISTRY: Dict[str, dict] = {}

# Traffic Control initial state
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

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

# Helper to run blocking DB commands on a thread pool executor
async def run_db(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

# ─────────────────────────────────────────────
# WEBSOCKET BROADCASTER
# ─────────────────────────────────────────────
async def broadcast_ws_json(payload: dict):
    dead = []
    for ws in WS_CLIENTS:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
            
    for ws in dead:
        if ws in WS_CLIENTS:
            WS_CLIENTS.remove(ws)

async def broadcast_telemetry(reading: dict):
    NODE_REGISTRY[reading["node_id"]] = reading
    await broadcast_ws_json({"type": "telemetry", "data": reading})

# ─────────────────────────────────────────────
# REST ENDPOINTS - BUILDING GEOMETRY (PostGIS / SQLite)
# ─────────────────────────────────────────────
@app.get("/api/v1/buildings/geojson")
def get_buildings_geojson(
    min_lon: Optional[float] = Query(None),
    min_lat: Optional[float] = Query(None),
    max_lon: Optional[float] = Query(None),
    max_lat: Optional[float] = Query(None),
    min_lng: Optional[float] = Query(None),
    max_lng: Optional[float] = Query(None)
):
    actual_min_lon = min_lon if min_lon is not None else min_lng
    actual_max_lon = max_lon if max_lon is not None else max_lng

    if None in (actual_min_lon, min_lat, actual_max_lon, max_lat):
        return {"type": "FeatureCollection", "features": []}

    weather = get_astana_weather()
    temp_out = weather["temp_out"]
    
    features = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if DB_BACKEND == "sqlite":
                cur.execute("""
                    SELECT id, osm_id, height, material, address, district,
                           facade_area_m2, roof_area_m2, window_area_m2, geom_geojson
                    FROM buildings;
                """)
                rows = cur.fetchall()
                for row in rows:
                    b_id, osm_id, height, material, address, district, facade_area, roof_area, window_area, geom_json_str = row
                    
                    # Thermal physical calculation (U-value = 1/R)
                    u_wall = 1.0 / 3.0 if material == "modern_ventilated" else 1.0 / 0.4
                    if material == "glass_curtain":
                        u_wall = 1.0 / 1.2
                    elif material == "brick_soviet":
                        u_wall = 1.0 / 0.8
                    elif material == "brezhnevka_panel":
                        u_wall = 1.0 / 0.7
                        
                    delta_t = 22.0 - temp_out
                    heat_loss_w = (u_wall * facade_area * delta_t)
                    heat_loss_w = max(heat_loss_w, 0.0)
                    
                    severity = "LOW"
                    if heat_loss_w >= 200000:
                        severity = "CRITICAL"
                    elif heat_loss_w >= 100000:
                        severity = "HIGH"
                    elif heat_loss_w >= 50000:
                        severity = "MODERATE"
                        
                    geom = json.loads(geom_json_str) if geom_json_str else None
                    if geom:
                        features.append({
                            "type": "Feature",
                            "geometry": geom,
                            "properties": {
                                "id": b_id,
                                "osm_id": osm_id,
                                "height": height,
                                "material": material,
                                "address": address,
                                "district": district,
                                "facade_area_m2": round(facade_area, 1),
                                "roof_area_m2": round(roof_area, 1),
                                "window_area_m2": round(window_area, 1),
                                "heat_loss_w": round(heat_loss_w, 1),
                                "severity": severity
                            }
                        })
            else:
                query = """
                    SELECT id, osm_id, height, material, address, district,
                           facade_area_m2, roof_area_m2, window_area_m2,
                           ST_AsGeoJSON(geom) as geojson
                    FROM buildings
                    WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                      AND ST_Intersects(geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
                    LIMIT 2000
                """
                params = [
                    actual_min_lon, min_lat, actual_max_lon, max_lat,
                    actual_min_lon, min_lat, actual_max_lon, max_lat
                ]
                cur.execute(query, params)
                rows = cur.fetchall()
                for row in rows:
                    b_id, osm_id, height, material, address, district, facade_area, roof_area, window_area, geom_json = row
                    
                    u_wall = 1.0 / 3.0 if material == "modern_ventilated" else 1.0 / 0.4
                    if material == "glass_curtain":
                        u_wall = 1.0 / 1.2
                    elif material == "brick_soviet":
                        u_wall = 1.0 / 0.8
                    elif material == "brezhnevka_panel":
                        u_wall = 1.0 / 0.7
                        
                    delta_t = 22.0 - temp_out
                    heat_loss_w = (u_wall * facade_area * delta_t)
                    heat_loss_w = max(heat_loss_w, 0.0)
                    
                    severity = "LOW"
                    if heat_loss_w >= 200000:
                        severity = "CRITICAL"
                    elif heat_loss_w >= 100000:
                        severity = "HIGH"
                    elif heat_loss_w >= 50000:
                        severity = "MODERATE"
                        
                    features.append({
                        "type": "Feature",
                        "geometry": json.loads(geom_json),
                        "properties": {
                            "id": b_id,
                            "osm_id": osm_id,
                            "height": height,
                            "material": material,
                            "address": address,
                            "district": district,
                            "facade_area_m2": round(facade_area, 1),
                            "roof_area_m2": round(roof_area, 1),
                            "window_area_m2": round(window_area, 1),
                            "heat_loss_w": round(heat_loss_w, 1),
                            "severity": severity
                        }
                    })
    except Exception as e:
        print(f"Error fetching buildings GeoJSON: {e}")
        raise HTTPException(status_code=500, detail="Database spatial query failed")
        
    return {"type": "FeatureCollection", "features": features}

@app.get("/api/v1/spatial/search")
def spatial_radius_search(
    lon: float = Query(...),
    lat: float = Query(...),
    radius_meters: float = Query(1000.0)
):
    results = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if DB_BACKEND == "sqlite":
                # Approximate distance in meters: 1 deg = 111320 meters
                cur.execute("SELECT id, address, material, facade_area_m2, geom_geojson FROM buildings;")
                rows = cur.fetchall()
                for r in rows:
                    b_id, address, material, facade_area, geom_json_str = r
                    if not geom_json_str:
                        continue
                    geom = json.loads(geom_json_str)
                    coords = geom["coordinates"][0]
                    lons = [c[0] for c in coords]
                    lats = [c[1] for c in coords]
                    b_lon = sum(lons) / len(lons)
                    b_lat = sum(lats) / len(lats)
                    
                    dx = (b_lon - lon) * 111320.0 * 0.6276
                    dy = (b_lat - lat) * 111320.0
                    dist = (dx*dx + dy*dy)**0.5
                    
                    if dist <= radius_meters:
                        results.append({
                            "id": b_id,
                            "address": address,
                            "material": material,
                            "facade_area_m2": round(facade_area, 1),
                            "distance_meters": round(dist, 1)
                        })
                results.sort(key=lambda x: x["distance_meters"])
            else:
                query = """
                    SELECT id, address, material, facade_area_m2,
                           ST_Distance(geom::geography, ST_MakePoint(%s, %s)::geography) as distance_meters
                    FROM buildings
                    WHERE ST_DWithin(geom::geography, ST_MakePoint(%s, %s)::geography, %s)
                    ORDER BY distance_meters ASC;
                """
                cur.execute(query, (lon, lat, lon, lat, radius_meters))
                rows = cur.fetchall()
                for r in rows:
                    results.append({
                        "id": r[0],
                        "address": r[1],
                        "material": r[2],
                        "facade_area_m2": round(r[3], 1),
                        "distance_meters": round(r[4], 1)
                    })
    except Exception as e:
        print(f"Spatial query error: {e}")
        raise HTTPException(status_code=500, detail="Proximity search failed")
    return results

@app.get("/api/v1/building/{building_id}/analysis")
def analyze_building(building_id: str):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, osm_id, height, material, address, district,
                       facade_area_m2, roof_area_m2, window_area_m2
                FROM buildings
                WHERE id = %s;
            """ if DB_BACKEND == "postgres" else """
                SELECT id, osm_id, height, material, address, district,
                       facade_area_m2, roof_area_m2, window_area_m2
                FROM buildings
                WHERE id = ?;
            """, (building_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Building not found")
                
            b_id, osm_id, height, material, address, district, facade_area, roof_area, window_area = row
            
            if DB_BACKEND == "postgres":
                cur.execute("""
                    SELECT time_bucket('1 hour', time) AS bucket,
                           avg(temp_in) as avg_temp_in,
                           avg(temp_out) as avg_temp_out,
                           avg(heat_loss) as avg_heat_loss
                    FROM telemetry
                    WHERE building_id = %s OR building_id = 'bld_esp32_hw_01'
                    GROUP BY bucket
                    ORDER BY bucket DESC
                    LIMIT 24;
                """, (building_id,))
            else:
                cur.execute("""
                    SELECT strftime('%Y-%m-%d %H:00:00', time) AS bucket,
                           avg(temp_in) as avg_temp_in,
                           avg(temp_out) as avg_temp_out,
                           avg(heat_loss) as avg_heat_loss
                    FROM telemetry
                    WHERE building_id = ? OR building_id = 'bld_esp32_hw_01'
                    GROUP BY bucket
                    ORDER BY bucket DESC
                    LIMIT 24;
                """, (building_id,))
            hist_rows = cur.fetchall()
    except Exception as e:
        print(f"Database query failed: {e}")
        raise HTTPException(status_code=500, detail="Database query failed")
        
    history = []
    for h in hist_rows:
        try:
            h_time = datetime.fromisoformat(h[0]).strftime("%H:%M") if DB_BACKEND == "sqlite" and h[0] else (h[0].strftime("%H:%M") if h[0] else "")
        except Exception:
            h_time = str(h[0])[-8:-3] if h[0] else ""
        history.append({
            "time": h_time,
            "temp_in": round(h[1], 1) if h[1] is not None else 22.0,
            "temp_out": round(h[2], 1) if h[2] is not None else -15.0,
            "heat_loss_kw": round(h[3]/1000.0, 2) if h[3] is not None else 0.0
        })
    history.reverse()
    
    tariff = 12.5  # KZT / kWh
    heating_days = 213
    
    u_wall_current = 1.0 / 0.4 if material == "khrushchyovka_panel" else 1.0 / 3.0
    if material == "brick_soviet":
        u_wall_current = 1.0 / 0.8
    elif material == "brezhnevka_panel":
        u_wall_current = 1.0 / 0.7
        
    u_wall_upgraded = 0.31
    cost_per_m2 = 5200 if material in ("khrushchyovka_panel", "brezhnevka_panel") else 3800
    
    dt_avg = 37.0
    loss_current_w = (u_wall_current * facade_area * dt_avg)
    loss_upgraded_w = (u_wall_upgraded * facade_area * dt_avg)
    
    saving_w = max(loss_current_w - loss_upgraded_w, 0.0)
    yearly_saving_kwh = (saving_w / 1000.0) * 24 * heating_days
    yearly_saving_kzt = yearly_saving_kwh * tariff
    
    insulation_cost_kzt = facade_area * cost_per_m2
    roi_years = insulation_cost_kzt / yearly_saving_kzt if yearly_saving_kzt > 0 else 99.0
    
    chart_years = []
    without_renov = []
    with_renov = []
    
    seasonal_baseline_cost = (loss_current_w / 1000.0) * 24 * heating_days * tariff
    seasonal_upgraded_cost = (loss_upgraded_w / 1000.0) * 24 * heating_days * tariff
    
    for year in range(6):
        chart_years.append(f"Год {year}")
        without_renov.append(round(seasonal_baseline_cost * year, 0))
        with_renov.append(round(insulation_cost_kzt + (seasonal_upgraded_cost * year), 0))
        
    return {
        "building_info": {
            "id": b_id, "address": address, "district": district, "material": material,
            "height": height, "facade_area_m2": round(facade_area, 1),
            "roof_area_m2": round(roof_area, 1), "window_area_m2": round(window_area, 1)
        },
        "metrics": {
            "insulation_type": "Минеральная вата (снаружи)",
            "estimated_cost_kzt": round(insulation_cost_kzt, 0),
            "yearly_saving_kzt": round(yearly_saving_kzt, 0),
            "roi_years": round(roi_years, 1),
            "roi_months": round(roi_years * 12, 1),
            "pitch": f"Утепление фасада здания {address} обойдется в {insulation_cost_kzt/1e6:.1f} млн ₸. Снижение теплопотерь сэкономит {yearly_saving_kzt:,.0f} ₸ за сезон. Срок окупаемости — {roi_years:.1f} года."
        },
        "history": history,
        "chart_data": {
            "years": chart_years,
            "without_renovation_accumulated_kzt": without_renov,
            "with_renovation_accumulated_kzt": with_renov
        }
    }

# ─────────────────────────────────────────────
# REST ENDPOINTS - ESP32 THERMO PROTOTYPE
# ─────────────────────────────────────────────
@app.post("/api/v1/esp32/telemetry")
async def receive_esp32_telemetry(payload: ESP32Payload):
    weather = get_astana_weather()
    wind_speed = weather["wind_speed"]
    humidity = payload.humidity if payload.humidity is not None else weather["humidity"]
    
    building_id = "bld_esp32_hw_01"
    facade_area = 1500.0
    material_preset = "khrushchyovka_panel"
    address = "ул. Сейфуллина, 24 [PROTOTYPE]"
    district = "Сарыарка"
    
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT facade_area_m2, material, address, district
                FROM buildings
                WHERE id = 'bld_esp32_hw_01'
                LIMIT 1;
            """)
            row = cur.fetchone()
            if row:
                facade_area, material_preset, address, district = row
    except Exception as e:
        print(f"Database fetch error during telemetry: {e}")
        
    r_val = 0.4 if material_preset == "khrushchyovka_panel" else 1.5
    if payload.window_open:
        r_val = 0.05
        
    delta_t = payload.t_in - payload.t_out
    actual_loss_w = (facade_area * delta_t) / r_val
    actual_loss_w = max(actual_loss_w, 0.0)
    actual_loss_kw = actual_loss_w / 1000.0
    
    is_anomaly, reason, expected_loss_kw = detect_anomaly(
        payload.t_in, payload.t_out, humidity, wind_speed, facade_area, material_preset, actual_loss_kw
    )
    
    try:
        with get_db() as conn:
            cur = conn.cursor()
            placeholder = "?" if DB_BACKEND == "sqlite" else "%s"
            now_val = datetime.now(timezone.utc).isoformat() if DB_BACKEND == "sqlite" else "NOW()"
            
            cur.execute(f"""
                INSERT INTO telemetry (time, building_id, temp_in, temp_out, heat_loss, is_anomaly, anomaly_reason)
                VALUES ({'?' if DB_BACKEND == "sqlite" else 'NOW()'}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder});
            """ if DB_BACKEND == "postgres" else f"""
                INSERT INTO telemetry (time, building_id, temp_in, temp_out, heat_loss, is_anomaly, anomaly_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (now_val, building_id, payload.t_in, payload.t_out, actual_loss_w, is_anomaly, reason) if DB_BACKEND == "sqlite" else (building_id, payload.t_in, payload.t_out, actual_loss_w, is_anomaly, reason))
    except Exception as e:
        print(f"Telemetry log insert failed: {e}")
        
    reading = {
        "node_id": payload.node_id,
        "building_id": building_id,
        "address": address,
        "district": district,
        "temp_facade_c": round(payload.t_in * 0.8 + payload.t_out * 0.2, 1),
        "temp_ambient_c": round(payload.t_out, 1),
        "humidity_pct": round(humidity, 1),
        "heat_loss_w": round(actual_loss_w, 1),
        "severity": "CRITICAL" if is_anomaly else ("HIGH" if actual_loss_w > 100000 else "LOW"),
        "is_hardware": True,
        "is_anomaly": is_anomaly,
        "anomaly_reason": reason,
        "timestamp": time.time()
    }
    
    await broadcast_telemetry(reading)
    return {"status": "ok", "anomaly": is_anomaly, "reason": reason}

@app.get("/api/v1/stats")
def get_system_stats():
    nodes = list(NODE_REGISTRY.values())
    hw_count = sum(1 for n in nodes if n.get("is_hardware"))
    virt_count = len(nodes) - hw_count
    weather = get_astana_weather()
    return {
        "total_nodes": len(nodes),
        "hardware_nodes": hw_count,
        "virtual_nodes": virt_count,
        "outside_temp": weather["temp_out"],
        "humidity": weather["humidity"],
        "wind_speed": weather["wind_speed"],
        "peak_heat_loss_w": max((n["heat_loss_w"] for n in nodes), default=0.0)
    }

# ─────────────────────────────────────────────
# REST ENDPOINTS - PORTED TRAFFIC SIMULATOR (y_prototype)
# ─────────────────────────────────────────────
@app.post("/api/telemetry")
async def receive_hardware_telemetry(data: HardwareTelemetry):
    control_decision = _local_smart_control(SmartControlRequest(
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
    await broadcast_ws_json(payload)
    await broadcast_ws_json({
        "source": "smart_control",
        "type": "control_decision",
        "payload": control_decision,
    })
    return {"status": "SUCCESS"}

@app.post("/api/twin/telemetry")
async def receive_twin_telemetry(data: TwinTelemetry):
    m = data.metrics
    is_anomaly, anomaly_score, confidence = detect_traffic_anomaly(
        m.traffic_speed_kmh, m.congestion_index, m.air_quality_co2_ppm, m.facade_heat_loss_w_m2, m.ambient_temp_c
    )

    await run_db(_save_traffic_log, {
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
    await broadcast_ws_json(payload)

    if data.ai_trigger or is_anomaly:
        control_decision = _local_smart_control(SmartControlRequest(
            district_id=data.district_id,
            mode="AUTO",
            metrics=m,
        ))
        smart_control_state.update(control_decision)
        await broadcast_ws_json({
            "source": "smart_control",
            "type": "control_decision",
            "payload": control_decision,
        })

    return {"status": "SUCCESS", "is_anomaly": is_anomaly}

# ─────────────────────────────────────────────
# SMART GRID TRAFFIC CONTROL OVERRIDES
# ─────────────────────────────────────────────
@app.get("/api/control/status")
async def get_control_status():
    return smart_control_state

@app.post("/api/control/decision")
async def create_control_decision(req: SmartControlRequest):
    decision = _local_smart_control(req)
    smart_control_state.update(decision)

    await run_db(_save_control_event, {
        "district_id": decision["district_id"],
        "mode": decision["mode"],
        "risk_level": decision["risk_level"],
        "signal_phase": decision["signal_phase"],
        "power_state": decision["power_state"],
        "power_usage_kw": decision["power_usage_kw"],
        "reason": decision["reason"],
        "action_json": json.dumps(decision["recommended_actions"]),
    })

    await broadcast_ws_json({
        "source": "smart_control",
        "type": "control_decision",
        "payload": decision,
    })
    return decision

@app.post("/api/control/manual")
async def manual_control(req: SmartControlRequest):
    if not req.manual_action:
        raise HTTPException(status_code=400, detail="manual_action is required")
    req.mode = "MANUAL"
    return await create_control_decision(req)

# ─────────────────────────────────────────────
# SMART CONTROL LOGIC ENGINE
# ─────────────────────────────────────────────
def _estimate_power_kw(metrics: Optional[TwinMetrics], hardware: dict) -> float:
    if hardware.get("power_kw") is not None:
        return round(float(hardware["power_kw"]), 2)
    if not metrics:
        return 0.0
    heat_component = max(0.0, metrics.facade_heat_loss_w_m2 - 70.0) * 0.035
    co2_component = max(0.0, metrics.air_quality_co2_ppm - 400.0) * 0.002
    temp_component = max(0.0, metrics.ambient_temp_c - 25.0) * 0.18
    return round(2.8 + heat_component + co2_component + temp_component, 2)

def _local_smart_control(req: SmartControlRequest) -> dict:
    metrics = req.metrics
    hardware = req.hardware or {}
    power_kw = _estimate_power_kw(metrics, hardware)
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

# ─────────────────────────────────────────────
# REST ENDPOINTS - TRAFFIC AI OPTIMIZATION (Gemini)
# ─────────────────────────────────────────────
@app.post("/api/analyze")
async def analyze_telemetry(payload: TelemetryPayload):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _local_traffic_fallback(payload)

    prompt = f"""You are the Chief AI Urban Logistics & Energy Efficiency Coordinator for Astana City.
Analyze this Astana Twin District Telemetry Snapshot:
- District: {payload.district_id}
- Avg Traffic Speed: {payload.metrics.traffic_speed_kmh} km/h
- Congestion Index: {payload.metrics.congestion_index}%
- Air Quality (CO2): {payload.metrics.air_quality_co2_ppm} PPM
- Facade Heat Loss: {payload.metrics.facade_heat_loss_w_m2} W/m²
- Ambient Temperature: {payload.metrics.ambient_temp_c}°C

Analyze the correlation between traffic speed/congestion (CO2 emissions) and building heat loss.
Return strictly in JSON:
{{
  "analysis": "detailed assessment in Russian",
  "recommendations": "concrete traffic light and thermal retrofit actions in Russian",
  "adjustments": [{{"roadId": "R1", "action": "GREEN_WAVE", "direction": "East-West", "duration": 15, "reason": "reason in Russian"}}],
  "efficiencyMetrics": {{"travelTimeReduction": 22, "co2Reduction": 14, "avgSpeedIncrease": 18}}
}}"""

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(api_url, json=body, timeout=25.0)
            if r.status_code != 200:
                raise HTTPException(status_code=502, detail="Gemini endpoint error")
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(clean_json_response(text))
        except Exception as e:
            logger.error("Gemini traffic analysis error: %s", e)
            return _local_traffic_fallback(payload)

def clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:] if lines[0].strip().startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].strip().startswith("```") else lines
        text = "\n".join(lines).strip()
    return text

def _local_traffic_fallback(payload: TelemetryPayload) -> dict:
    co2   = payload.metrics.air_quality_co2_ppm
    speed = payload.metrics.traffic_speed_kmh
    loss  = payload.metrics.facade_heat_loss_w_m2

    analysis = f"[Local AI] Уровень CO₂: {co2:.0f} PPM. Средняя скорость: {speed:.1f} км/ч. Теплопотери фасада: {loss:.0f} Вт/м²."
    recs     = "Параметры в пределах нормы. Регулировка светофоров стандартная."
    adjs     = []
    eff      = {"travelTimeReduction": 5, "co2Reduction": 4, "avgSpeedIncrease": 6}

    if co2 > 700:
        analysis += f" ⚠️ Критическое скопление CO₂ на перекрёстке Node-A."
        recs      = "Активировать режим «Зелёная волна» для разгрузки перекрёстка Node-A."
        adjs      = [{"roadId": "R2", "action": "GREEN_WAVE", "direction": "East-West", "duration": 25, "reason": "CO₂ Node-A разгрузка"},
                     {"roadId": "R5", "action": "BUS_PRIORITY", "direction": "North-South", "duration": 15, "reason": "Приоритет BRT обхода"}]
        eff       = {"travelTimeReduction": 24, "co2Reduction": 18, "avgSpeedIncrease": 20}
    elif loss > 130:
        analysis += f" Высокие теплопотери ({loss:.0f} Вт/м²)."
        recs      = "Рекомендован локальный аудит изоляции фасадов."
        adjs      = [{"roadId": "R1", "action": "GREEN_WAVE", "direction": "East-West", "duration": 10, "reason": "Номинальный режим"}]
        eff       = {"travelTimeReduction": 8, "co2Reduction": 6, "avgSpeedIncrease": 7}

    return {"analysis": analysis, "recommendations": recs, "adjustments": adjs, "efficiencyMetrics": eff}

# ─────────────────────────────────────────────
# REST ENDPOINTS - THERMO AI ANALYSIS (Gemini)
# ─────────────────────────────────────────────
@app.post("/api/analyze-thermo")
async def analyze_thermo(payload: ThermoPayload):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        result = _local_thermo_fallback(payload)
    else:
        prompt = f"""You are the Senior AI Building Energy Efficiency Consultant for Astana Municipality.
Analyze the following building thermal loss configuration:
- Building ID: {payload.building_id}
- Building Name: {payload.name}
- Construction Year: {payload.age}
- Current Heat Loss: {payload.current_loss_wm2} W/m²
- Installed Insulation: {payload.insulation_type}
- Simulated Upgrade Thickness: {payload.target_thickness_mm} mm
- Estimated Heat Loss Reduction: {payload.calculated_reduction_percent}%

Recommend specific building envelope retrofits for Astana's sub-zero climate (-30°C winters).
Return strictly in JSON:
{{
  "analysis": "detailed thermal loss assessment in Russian",
  "recommendations": "insulation material and installation recommendations in Russian",
  "kpi": {{"annualCo2ReductionTons": 4.8, "annualCostSavingKzt": 340000}}
}}"""

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}

        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(api_url, json=body, timeout=25.0)
                if r.status_code != 200:
                    raise HTTPException(status_code=502, detail="Gemini endpoint error")
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                result = json.loads(clean_json_response(text))
            except Exception as e:
                logger.error("Gemini thermo analysis error: %s", e)
                result = _local_thermo_fallback(payload)

    await run_db(_save_thermo_log, {
        "building_id":              payload.building_id,
        "building_name":            payload.name,
        "construction_year":        payload.age,
        "base_heat_loss_wm2":       payload.current_loss_wm2,
        "insulation_type":          payload.insulation_type,
        "insulation_thickness_mm":  payload.target_thickness_mm,
        "reduction_percent":        payload.calculated_reduction_percent,
        "annual_co2_tons":          result.get("kpi", {}).get("annualCo2ReductionTons", 0),
        "annual_savings_kzt":       result.get("kpi", {}).get("annualCostSavingKzt", 0),
        "ai_analysis":              result.get("analysis", ""),
        "ai_recommendations":       result.get("recommendations", ""),
    })

    return result

def _local_thermo_fallback(payload: ThermoPayload) -> dict:
    saved   = payload.current_loss_wm2 * (payload.calculated_reduction_percent / 100.0)
    co2     = round(saved * 0.045, 1)
    savings = int(saved * 2300)
    return {
        "analysis": f"[Local AI] Аудит {payload.name} ({payload.age} г.). Теплопотери {payload.current_loss_wm2} Вт/м² — признак устаревшего теплового контура ({payload.insulation_type}).",
        "recommendations": f"Монтаж утеплителя {payload.target_thickness_mm} мм. Рекомендуются плиты базальтовой ваты (≥110 кг/м³) для климата Астаны (-30°C зима).",
        "kpi": {"annualCo2ReductionTons": co2, "annualCostSavingKzt": savings}
    }

# ─────────────────────────────────────────────
# REST ENDPOINTS - AI CHAT ADVISOR WITH HISTORY
# ─────────────────────────────────────────────
@app.post("/api/chat")
async def ai_chat(req: ChatRequest):
    api_key = os.getenv("GEMINI_API_KEY")

    await run_db(_save_chat_message, req.session_id, req.mode, "user", req.message, req.context)
    history_rows = await run_db(_fetch_chat_history, req.session_id, req.mode, 12)

    if not api_key:
        reply = _local_chat_fallback(req.message, req.mode, req.context)
    else:
        reply = await _call_gemini_chat(api_key, req.message, req.mode, req.context, history_rows)

    await run_db(_save_chat_message, req.session_id, req.mode, "assistant", reply, {})
    return {"reply": reply, "session_id": req.session_id, "mode": req.mode}

async def _call_gemini_chat(api_key: str, user_msg: str, mode: str, context: dict, history: list) -> str:
    if mode == "traffic":
        system = f"""Ты — AI-координатор дорожного движения системы KHA-DIVERGENT для Астаны.
Текущие данные телеметрии:
• Средняя скорость: {context.get('avgSpeed', '?')} км/ч
• Индекс заторов: {context.get('congestionRate', '?')}%
• CO₂: {context.get('co2Ppm', '?')} PPM
• Теплопотери фасадов: {context.get('facadeHeatLoss', '?')} Вт/м²
• Температура: {context.get('ambientTemp', '?')}°C
• Активные AI-регулировки: {context.get('appliedAdjustments', 'нет')}
Дорожная сеть: R1=Turan Ave, R2=Kabanbay Batyr, R3=Mangilik El, R4=Kunayev St, R5=Dostyk St, R6=Syganak St.
Отвечай кратко (2-4 предложения). Можешь рекомендовать действия: GREEN_WAVE, BUS_PRIORITY, EMERGENCY_CORRIDOR на дорогах R1-R6."""
    else:
        b = context.get("selectedBuilding") or {}
        system = f"""Ты — AI-консультант по энергоэффективности зданий для Астаны, система KHA-DIVERGENT.
Данные выбранного здания: {b.get('name','?')} (ID: {b.get('id','?')}), год постройки: {b.get('age','?')},
изоляция: {b.get('insulation','?')}, теплопотери: {b.get('h0','?')} Вт/м².
Климат Астаны: -30°C зима, +35°C лето. Норма теплопотерь: <80 Вт/м².
Отвечай кратко (2-4 предложения). Давай конкретные рекомендации по материалам (базальтовая вата, EPS, PIR-плиты, полиуретан)."""

    contents = []
    for row in history[-8:]:
        gemini_role = "user" if row["role"] == "user" else "model"
        contents.append({"role": gemini_role, "parts": [{"text": row["content"]}]})

    contents.append({"role": "user", "parts": [{"text": system + "\n\nВопрос: " + user_msg}]})

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(api_url, json={"contents": contents}, timeout=20.0)
            if r.status_code != 200:
                raise Exception(f"Gemini returned {r.status_code}")
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error("Gemini chat error: %s", e)
            return _local_chat_fallback(user_msg, mode, context)

def _local_chat_fallback(msg: str, mode: str, ctx: dict) -> str:
    m = msg.lower()
    if mode == "traffic":
        speed = ctx.get("avgSpeed", 0)
        co2   = ctx.get("co2Ppm", 0)
        cong  = ctx.get("congestionRate", 0)
        if any(k in m for k in ["congestion", "пробка", "затор", "traffic"]):
            status = "⚠️ Высокая загрузка" if cong > 50 else "✅ Нормальный поток"
            return f"{status}. Индекс заторов: {cong}%. {'Рекомендую GREEN_WAVE на R1 (Turan Ave).' if cong > 50 else 'Светофоры в стандартном режиме.'}"
        if any(k in m for k in ["co2", "air", "воздух", "выброс"]):
            return f"CO₂: {co2:.0f} PPM. {'⚠️ Превышение нормы — рекомендую разгрузку R2.' if co2 > 600 else '✅ В норме (<450 PPM).'}"
        if any(k in m for k in ["speed", "скорость", "быстро"]):
            return f"Средняя скорость по 6 коридорам: {speed:.1f} км/ч. {'Трафик замедлен.' if speed < 35 else 'Трафик в норме.'}"
        return f"Статус: скорость {speed:.1f} км/ч, заторы {cong}%, CO₂ {co2:.0f} PPM. Добавьте Gemini API ключ в .env для детального анализа."
    else:
        b = ctx.get("selectedBuilding") or {}
        if not b:
            return "Пожалуйста, выберите здание на карте для получения теплового анализа."
        h0 = b.get('h0', 0)
        if any(k in m for k in ["insulation", "изоляция", "утеплитель", "материал"]):
            return f"Для {b.get('name','здания')} ({h0} Вт/м²): рекомендую базальтовую вату 120-150 мм для климата Астаны. Текущая: {b.get('insulation','неизвестно')}."
        if any(k in m for k in ["cost", "стоимость", "экономия", "savings", "окупаемость"]):
            savings = round(h0 * 0.4 * 2300)
            return f"Расчётная экономия для {b.get('name','здания')}: ~{savings:,} KZT/год с утеплением 150 мм. Окупаемость ~4-6 лет."
        if any(k in m for k in ["rating", "класс", "energy", "энергия"]):
            rating = "A" if h0 < 55 else "B" if h0 < 90 else "C" if h0 < 130 else "D" if h0 < 185 else "E"
            return f"{b.get('name','Здание')} — энергокласс {rating} ({h0} Вт/м²). Целевой стандарт СНИП РК: <80 Вт/м²."
        return f"{b.get('name','Здание')} ({b.get('id','?')}): теплопотери {h0} Вт/м², год {b.get('age','?')}, изоляция: {b.get('insulation','?')}. Добавьте Gemini API ключ в .env для полного анализа."

# ─────────────────────────────────────────────
# REST ENDPOINTS - HISTORY & LOG READERS
# ─────────────────────────────────────────────
@app.get("/api/history/traffic")
async def get_traffic_history(limit: int = 50):
    records = await run_db(_fetch_traffic_history, limit)
    return {"records": records, "count": len(records)}

@app.get("/api/history/thermo")
async def get_thermo_history(limit: int = 30):
    records = await run_db(_fetch_thermo_history, limit)
    return {"records": records, "count": len(records)}

@app.get("/api/history/chat")
async def get_chat_history(session_id: str = "default", mode: str = "traffic", limit: int = 30):
    records = await run_db(_fetch_chat_history, session_id, mode, limit)
    return {"records": records, "session_id": session_id, "mode": mode}

@app.get("/api/history/control")
async def get_control_history(limit: int = 30):
    records = await run_db(_fetch_control_history, limit)
    return {"records": records, "count": len(records)}

@app.get("/api/db/stats")
async def get_db_stats():
    stats = await run_db(_fetch_db_stats)
    return stats

@app.get("/api/config")
async def get_config():
    return {"gemini_active": bool(os.getenv("GEMINI_API_KEY"))}

@app.get("/api/forecast")
async def get_forecast():
    conn = get_db().__enter__()
    try:
        if DB_BACKEND == "sqlite":
            df = pd.read_sql_query("""
                SELECT ts, traffic_speed, co2_ppm
                FROM traffic_logs
                WHERE datetime(ts) >= datetime('now', '-5 minutes')
                ORDER BY ts ASC
            """, conn)
        else:
            df = pd.read_sql_query("""
                SELECT ts, traffic_speed, co2_ppm 
                FROM traffic_logs 
                WHERE ts >= NOW() - INTERVAL '5 minutes'
                ORDER BY ts ASC
            """, conn)
    except Exception as e:
        print(f"Error loading telemetry for forecast: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()
    
    if df.empty or len(df) < 10:
        return {"speed_forecast": [], "co2_forecast": [], "status": "insufficient_data"}
        
    df['ds'] = pd.to_datetime(df['ts']).dt.tz_localize(None)
    
    speed_forecast_list = []
    co2_forecast_list = []
    status = "success"
    
    try:
        from prophet import Prophet
        import logging
        logging.getLogger('prophet').setLevel(logging.ERROR)
        logging.getLogger('cmdstanpy').setLevel(logging.ERROR)
        
        df_speed = df[['ds', 'traffic_speed']].rename(columns={'traffic_speed': 'y'})
        m_speed = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False)
        m_speed.fit(df_speed)
        future_speed = m_speed.make_future_dataframe(periods=30, freq='s', include_history=False)
        forecast_speed = m_speed.predict(future_speed)
        speed_forecast_list = forecast_speed[['ds', 'yhat']].to_dict(orient="records")
        
        df_co2 = df[['ds', 'co2_ppm']].rename(columns={'co2_ppm': 'y'})
        m_co2 = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False)
        m_co2.fit(df_co2)
        future_co2 = m_co2.make_future_dataframe(periods=30, freq='s', include_history=False)
        forecast_co2 = m_co2.predict(future_co2)
        co2_forecast_list = forecast_co2[['ds', 'yhat']].to_dict(orient="records")
    except Exception as e:
        logger.error("Prophet forecasting failed, using fallback trend: %s", e)
        last_ts = df['ds'].iloc[-1]
        last_speed = df['traffic_speed'].iloc[-1]
        last_co2 = df['co2_ppm'].iloc[-1]
        
        speed_trend = (df['traffic_speed'].iloc[-1] - df['traffic_speed'].iloc[0]) / len(df) if len(df) > 1 else 0
        co2_trend = (df['co2_ppm'].iloc[-1] - df['co2_ppm'].iloc[0]) / len(df) if len(df) > 1 else 0
        
        for i in range(1, 31):
            ds_future = last_ts + pd.Timedelta(seconds=i)
            speed_forecast_list.append({
                "ds": ds_future,
                "yhat": max(5.0, min(80.0, last_speed + speed_trend * i))
            })
            co2_forecast_list.append({
                "ds": ds_future,
                "yhat": max(300.0, min(1200.0, last_co2 + co2_trend * i))
            })
        status = "fallback"

    for item in speed_forecast_list:
        item['ds'] = item['ds'].strftime("%Y-%m-%dT%H:%M:%SZ")
    for item in co2_forecast_list:
        item['ds'] = item['ds'].strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "speed_forecast": speed_forecast_list,
        "co2_forecast": co2_forecast_list,
        "status": status
    }

# ─────────────────────────────────────────────
# DATABASE IMPLEMENTATION DETAILS (GETTERS & WRITERS)
# ─────────────────────────────────────────────
def _save_traffic_log(row: dict):
    with get_db() as conn:
        cur = conn.cursor()
        if DB_BACKEND == "sqlite":
            cur.execute("""
                INSERT INTO traffic_logs
                    (district_id, traffic_speed, congestion_index, co2_ppm,
                     heat_loss_wm2, ambient_temp_c, is_anomaly, anomaly_score, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["district_id"], row["traffic_speed"], row["congestion_index"], row["co2_ppm"],
                row["heat_loss_wm2"], row["ambient_temp_c"], row["is_anomaly"], row["anomaly_score"], row["source"]
            ))
        else:
            cur.execute("""
                INSERT INTO traffic_logs
                    (district_id, traffic_speed, congestion_index, co2_ppm,
                     heat_loss_wm2, ambient_temp_c, is_anomaly, anomaly_score, source)
                VALUES
                    (%(district_id)s, %(traffic_speed)s, %(congestion_index)s, %(co2_ppm)s,
                     %(heat_loss_wm2)s, %(ambient_temp_c)s, %(is_anomaly)s, %(anomaly_score)s, %(source)s)
            """, row)

def _save_thermo_log(row: dict):
    with get_db() as conn:
        cur = conn.cursor()
        if DB_BACKEND == "sqlite":
            cur.execute("""
                INSERT INTO thermo_logs
                    (building_id, building_name, construction_year, base_heat_loss_wm2,
                     insulation_type, insulation_thickness_mm, reduction_percent,
                     annual_co2_tons, annual_savings_kzt, ai_analysis, ai_recommendations)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["building_id"], row["building_name"], row["construction_year"], row["base_heat_loss_wm2"],
                row["insulation_type"], row["insulation_thickness_mm"], row["reduction_percent"],
                row["annual_co2_tons"], row["annual_savings_kzt"], row["ai_analysis"], row["ai_recommendations"]
            ))
        else:
            cur.execute("""
                INSERT INTO thermo_logs
                    (building_id, building_name, construction_year, base_heat_loss_wm2,
                     insulation_type, insulation_thickness_mm, reduction_percent,
                     annual_co2_tons, annual_savings_kzt, ai_analysis, ai_recommendations)
                VALUES
                    (%(building_id)s, %(building_name)s, %(construction_year)s, %(base_heat_loss_wm2)s,
                     %(insulation_type)s, %(insulation_thickness_mm)s, %(reduction_percent)s,
                     %(annual_co2_tons)s, %(annual_savings_kzt)s, %(ai_analysis)s, %(ai_recommendations)s)
            """, row)

def _save_chat_message(session_id: str, mode: str, role: str, content: str, context: dict):
    with get_db() as conn:
        cur = conn.cursor()
        placeholder = "?" if DB_BACKEND == "sqlite" else "%s"
        cur.execute(f"""
            INSERT INTO chat_history (session_id, mode, role, content, context)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
        """, (session_id, mode, role, content, json.dumps(context)))

def _save_control_event(row: dict):
    with get_db() as conn:
        cur = conn.cursor()
        if DB_BACKEND == "sqlite":
            cur.execute("""
                INSERT INTO control_events
                    (district_id, mode, risk_level, signal_phase, power_state,
                     power_usage_kw, reason, action_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["district_id"], row["mode"], row["risk_level"], row["signal_phase"], row["power_state"],
                row["power_usage_kw"], row["reason"], row["action_json"]
            ))
        else:
            cur.execute("""
                INSERT INTO control_events
                    (district_id, mode, risk_level, signal_phase, power_state,
                     power_usage_kw, reason, action_json)
                VALUES
                    (%(district_id)s, %(mode)s, %(risk_level)s, %(signal_phase)s, %(power_state)s,
                     %(power_usage_kw)s, %(reason)s, %(action_json)s)
            """, row)

def _fetch_traffic_history(limit: int = 50) -> list:
    with get_db() as conn:
        placeholder = "?" if DB_BACKEND == "sqlite" else "%s"
        df = pd.read_sql_query(
            f"SELECT * FROM traffic_logs ORDER BY id DESC LIMIT {placeholder}",
            conn, params=(limit,)
        )
    if 'ts' in df.columns:
        df['ts'] = pd.to_datetime(df['ts']).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df.to_dict(orient="records")

def _fetch_thermo_history(limit: int = 50) -> list:
    with get_db() as conn:
        placeholder = "?" if DB_BACKEND == "sqlite" else "%s"
        df = pd.read_sql_query(
            f"SELECT * FROM thermo_logs ORDER BY id DESC LIMIT {placeholder}",
            conn, params=(limit,)
        )
    if 'ts' in df.columns:
        df['ts'] = pd.to_datetime(df['ts']).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df.to_dict(orient="records")

def _fetch_chat_history(session_id: str, mode: str, limit: int = 30) -> list:
    with get_db() as conn:
        placeholder = "?" if DB_BACKEND == "sqlite" else "%s"
        df = pd.read_sql_query(f"""
            SELECT id, ts, role, content, context
            FROM chat_history
            WHERE session_id = {placeholder} AND mode = {placeholder}
            ORDER BY id DESC LIMIT {placeholder}
        """, conn, params=(session_id, mode, limit))
    if 'ts' in df.columns:
        df['ts'] = pd.to_datetime(df['ts']).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df.iloc[::-1].to_dict(orient="records")

def _fetch_control_history(limit: int = 30) -> list:
    with get_db() as conn:
        placeholder = "?" if DB_BACKEND == "sqlite" else "%s"
        df = pd.read_sql_query(
            f"SELECT * FROM control_events ORDER BY id DESC LIMIT {placeholder}",
            conn, params=(limit,)
        )
    if 'ts' in df.columns:
        df['ts'] = pd.to_datetime(df['ts']).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df.to_dict(orient="records")

def _fetch_db_stats() -> dict:
    with get_db() as conn:
        stats = {}
        for table in ("traffic_logs", "thermo_logs", "chat_history", "control_events"):
            try:
                df = pd.read_sql_query(f"SELECT COUNT(*) as cnt FROM {table}", conn)
                stats[table] = int(df["cnt"].iloc[0])
            except Exception:
                stats[table] = 0
                
        try:
            df_t = pd.read_sql_query(
                "SELECT traffic_speed, congestion_index, co2_ppm FROM traffic_logs ORDER BY id DESC LIMIT 100",
                conn
            )
        except Exception:
            df_t = pd.DataFrame()
            
    if not df_t.empty:
        stats["traffic_analytics"] = {
            "avg_speed_100":    round(float(df_t["traffic_speed"].mean()), 2),
            "avg_congestion":   round(float(df_t["congestion_index"].mean()), 2),
            "avg_co2":          round(float(df_t["co2_ppm"].mean()), 2),
            "max_co2":          round(float(df_t["co2_ppm"].max()), 2),
            "min_speed":        round(float(df_t["traffic_speed"].min()), 2),
        }
    else:
        stats["traffic_analytics"] = {
            "avg_speed_100": 50.0, "avg_congestion": 25.0, "avg_co2": 410.0, "max_co2": 450.0, "min_speed": 40.0
        }
    return stats

# ─────────────────────────────────────────────
# WEBSOCKET CONNECTIONS (Supporting both /ws and /ws/telemetry)
# ─────────────────────────────────────────────
async def handle_websocket_connection(websocket: WebSocket, prefix_type: str = "init"):
    await websocket.accept()
    WS_CLIENTS.append(websocket)
    logger.info(f"WS client connected ({prefix_type}) — total: {len(WS_CLIENTS)}")
    try:
        await websocket.send_json({
            "type": "init",
            "data": {
                "nodes": list(NODE_REGISTRY.values())
            }
        })
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            if msg.get("type") == "sensor_reading":
                reading = msg["data"]
                reading["timestamp"] = time.time()
                await broadcast_telemetry(reading)
            elif msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in WS_CLIENTS:
            WS_CLIENTS.remove(websocket)
        logger.info(f"WS client disconnected — total: {len(WS_CLIENTS)}")

@app.websocket("/ws")
async def websocket_ws(websocket: WebSocket):
    await handle_websocket_connection(websocket, "legacy")

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await handle_websocket_connection(websocket, "telemetry")

# ─────────────────────────────────────────────
# STATIC FILE SERVING
# ─────────────────────────────────────────────
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
else:
    _frontend = Path(__file__).resolve().parent.parent.parent / "frontend"
    if _frontend.is_dir():
         app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
