import json
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.database import get_db, init_db
from app.osm_ingest import ingest_data
from app.weather import get_astana_weather
from app.ml_anomaly import detect_anomaly
from app.weather_worker import weather_polling_worker
from app.websocket_server import websocket_streamer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize PostGIS and TimescaleDB tables
    init_db()
    
    # 2. Automatically ingest OSM buildings if database is empty
    try:
        count = 0
        with get_db() as conn:
            with conn.cursor() as cur:
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

app = FastAPI(
    title="TermoAstana API", 
    version="3.0", 
    description="Digital Thermal Twin of Astana - PostGIS & TimescaleDB Enabled",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections
WS_CLIENTS: List[WebSocket] = []
NODE_REGISTRY: Dict[str, dict] = {}

async def broadcast_telemetry(reading: dict):
    # Store reading in global registry
    NODE_REGISTRY[reading["node_id"]] = reading
    
    # Send to all connected WebSocket clients
    dead = []
    for ws in WS_CLIENTS:
        try:
            await ws.send_json({"type": "telemetry", "data": reading})
        except Exception:
            dead.append(ws)
            
    for ws in dead:
        if ws in WS_CLIENTS:
            WS_CLIENTS.remove(ws)

# --- FastAPI REST API ---

@app.get("/api/v1/buildings/geojson")
def get_buildings_geojson(
    min_lon: Optional[float] = Query(None),
    min_lat: Optional[float] = Query(None),
    max_lon: Optional[float] = Query(None),
    max_lat: Optional[float] = Query(None),
    min_lng: Optional[float] = Query(None),
    max_lng: Optional[float] = Query(None)
):
    """
    Returns buildings in GeoJSON FeatureCollection format.
    Filters using PostGIS ST_MakeEnvelope & ST_Intersects with a maximum limit of 2000 features to prevent OOM/payload bloat.
    """
    actual_min_lon = min_lon if min_lon is not None else min_lng
    actual_max_lon = max_lon if max_lon is not None else max_lng

    if None in (actual_min_lon, min_lat, actual_max_lon, max_lat):
        return {
            "type": "FeatureCollection",
            "features": []
        }

    weather = get_astana_weather()
    temp_out = weather["temp_out"]
    
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
        
    features = []
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                
                for row in rows:
                    b_id, osm_id, height, material, address, district, facade_area, roof_area, window_area, geom_json = row
                    
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
                    
                    # Determine severity classification
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
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

@app.get("/api/v1/spatial/search")
def spatial_radius_search(
    lon: float = Query(...),
    lat: float = Query(...),
    radius_meters: float = Query(1000.0)
):
    """
    GIS Spatial Search: returns buildings within a specific radius of a coordinate using PostGIS.
    """
    query = """
        SELECT id, address, material, facade_area_m2,
               ST_Distance(geom::geography, ST_MakePoint(%s, %s)::geography) as distance_meters
        FROM buildings
        WHERE ST_DWithin(geom::geography, ST_MakePoint(%s, %s)::geography, %s)
        ORDER BY distance_meters ASC;
    """
    results = []
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
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
        raise HTTPException(status_code=500, detail="PostGIS proximity query failed")
    return results

@app.get("/api/v1/building/{building_id}/analysis")
def analyze_building(building_id: str):
    """
    Computes energy profile, queries TimescaleDB time-series logs, and generates ROI payback curves.
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # 1. Fetch building characteristics
                cur.execute("""
                    SELECT id, osm_id, height, material, address, district,
                           facade_area_m2, roof_area_m2, window_area_m2
                    FROM buildings
                    WHERE id = %s;
                """, (building_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Building not found")
                    
                b_id, osm_id, height, material, address, district, facade_area, roof_area, window_area = row
                
                # 2. Fetch last 24 hours of hourly aggregated telemetry from TimescaleDB
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
                hist_rows = cur.fetchall()
    except Exception as e:
        print(f"Database query failed: {e}")
        raise HTTPException(status_code=500, detail="Database query failed")
        
    history = []
    for h in hist_rows:
        history.append({
            "time": h[0].strftime("%H:%M") if h[0] else "",
            "temp_in": round(h[1], 1) if h[1] is not None else 22.0,
            "temp_out": round(h[2], 1) if h[2] is not None else -15.0,
            "heat_loss_kw": round(h[3]/1000.0, 2) if h[3] is not None else 0.0
        })
    history.reverse()
    
    # 3. Calculate ROI Calculations
    tariff = 12.5  # KZT / kWh (Astanaenergosbyt)
    heating_days = 213
    
    # Establish U-Values
    u_wall_current = 1.0 / 0.4 if material == "khrushchyovka_panel" else 1.0 / 3.0
    if material == "brick_soviet":
        u_wall_current = 1.0 / 0.8
    elif material == "brezhnevka_panel":
        u_wall_current = 1.0 / 0.7
        
    u_wall_upgraded = 0.31  # SNiP threshold
    cost_per_m2 = 5200 if material in ("khrushchyovka_panel", "brezhnevka_panel") else 3800
    
    # Baseline calculations
    dt_avg = 37.0  # inside 22C, average outside -15C
    loss_current_w = u_wall_current * facade_area * dt_avg
    loss_upgraded_w = u_wall_upgraded * facade_area * dt_avg
    
    saving_w = max(loss_current_w - loss_upgraded_w, 0.0)
    yearly_saving_kwh = (saving_w / 1000.0) * 24 * heating_days
    yearly_saving_kzt = yearly_saving_kwh * tariff
    
    insulation_cost_kzt = facade_area * cost_per_m2
    roi_years = insulation_cost_kzt / yearly_saving_kzt if yearly_saving_kzt > 0 else 99.0
    
    # Build chart data
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
            "id": b_id,
            "address": address,
            "district": district,
            "material": material,
            "height": height,
            "facade_area_m2": round(facade_area, 1),
            "roof_area_m2": round(roof_area, 1),
            "window_area_m2": round(window_area, 1)
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

class ESP32Payload(BaseModel):
    node_id: str
    t_in: float
    t_out: float
    window_open: bool
    humidity: Optional[float] = None

@app.post("/api/v1/esp32/telemetry")
async def receive_esp32_telemetry(payload: ESP32Payload):
    """
    Receives raw sensor readings from ESP32, calculates heat losses, 
    detects anomalies via RandomForest ML inference, logs to TimescaleDB, and broadcasts.
    """
    weather = get_astana_weather()
    wind_speed = weather["wind_speed"]
    humidity = payload.humidity if payload.humidity is not None else weather["humidity"]
    
    # Target hardware building values
    building_id = "bld_esp32_hw_01"
    facade_area = 1500.0
    material_preset = "khrushchyovka_panel"
    address = "ул. Сейфуллина, 24 [PROTOTYPE]"
    district = "Сарыарка"
    
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
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
        
    # Standard base resistance
    r_val = 0.4 if material_preset == "khrushchyovka_panel" else 1.5
    if payload.window_open:
        # Window open drops thermal resistance to a fraction (simulates draft heat escape)
        r_val = 0.05
        
    delta_t = payload.t_in - payload.t_out
    actual_loss_w = (facade_area * delta_t) / r_val
    actual_loss_w = max(actual_loss_w, 0.0)
    actual_loss_kw = actual_loss_w / 1000.0
    
    # Run ML anomaly detection (RandomForest Regressor)
    is_anomaly, reason, expected_loss_kw = detect_anomaly(
        payload.t_in, payload.t_out, humidity, wind_speed, facade_area, material_preset, actual_loss_kw
    )
    
    # Log time-series telemetry to TimescaleDB
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO telemetry (time, building_id, temp_in, temp_out, heat_loss, is_anomaly, anomaly_reason)
                    VALUES (NOW(), %s, %s, %s, %s, %s, %s);
                """, (building_id, payload.t_in, payload.t_out, actual_loss_w, is_anomaly, reason))
    except Exception as e:
        print(f"TimescaleDB insert failed: {e}")
        
    # Node registry broadcast reading format
    reading = {
        "node_id": payload.node_id,
        "building_id": building_id,
        "address": address,
        "district": district,
        "temp_facade_c": round(payload.t_in * 0.8 + payload.t_out * 0.2, 1), # Est facade temp
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
    """Aggregates system KPIs, counting live hardware nodes and virtual nodes."""
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

# --- WebSockets ---

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    WS_CLIENTS.append(websocket)
    try:
        # Send initial registry
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
                # Simulated telemetry coming from iot_emulator.py
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

# Mount frontend build directory
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
else:
    # Mount frontend root just in case static assets are served during development
    _frontend = Path(__file__).resolve().parent.parent.parent / "frontend"
    if _frontend.is_dir():
         app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
