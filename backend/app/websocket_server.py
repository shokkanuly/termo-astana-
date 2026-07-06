import asyncio
import time
import random
import math
from app.weather_worker import GLOBAL_WEATHER
from app.thermal_engine import calculate_baseline_heat_loss, load_simulation_buildings

def severity_from_w(w: float) -> str:
    if w >= 200000:
        return "CRITICAL"
    if w >= 100000:
        return "HIGH"
    if w >= 50000:
        return "MODERATE"
    return "LOW"

async def websocket_streamer():
    """
    Main 1-second WebSocket loop.
    Loads active buildings, computes their baselines when weather changes,
    applies Gaussian noise, and broadcasts to all connected WS clients.
    """
    print("WebSocket Physics Streamer: Task started.")
    
    # Wait for DB initialization to complete
    await asyncio.sleep(6)
    buildings = load_simulation_buildings()
    print(f"WebSocket Physics Streamer: Loaded {len(buildings)} simulation buildings.")
    
    cached_t_out = None
    baselines = {}
    
    tick = 0
    while True:
        try:
            t_out = GLOBAL_WEATHER["temp_out"]
            
            # Recalculate if weather updated or baselines empty
            if t_out != cached_t_out or not baselines:
                print(f"WebSocket Physics Streamer: Recalculating heat loss baselines for T_out={t_out}°C")
                buildings = load_simulation_buildings()
                for b in buildings:
                    baseline = calculate_baseline_heat_loss(b["facade_area"], b["material"], t_out)
                    baselines[b["building_id"]] = baseline
                cached_t_out = t_out
            
            # Retrieve clients dynamically to avoid circular import issues
            from app.main import WS_CLIENTS, NODE_REGISTRY
            
            if WS_CLIENTS and buildings:
                tick += 1
                for b in buildings:
                    baseline = baselines.get(b["building_id"], 10000.0)
                    
                    # Apply Gaussian noise (2% standard deviation)
                    noisy_loss = random.gauss(baseline, baseline * 0.02)
                    noisy_loss = max(noisy_loss, 0.0)
                    
                    # Simulate realistic facade temperature sensor fluctuations
                    ambient = t_out + math.sin(tick / 20.0) * 1.5
                    facade_temp = ambient + (21.0 - ambient) * (0.15 + random.uniform(0.01, 0.05))
                    
                    reading = {
                        "building_id": b["building_id"],
                        "node_id": b["node_id"],
                        "district": b["district"],
                        "address": b["address"],
                        "temp_facade_c": round(facade_temp, 1),
                        "temp_ambient_c": round(ambient, 1),
                        "humidity_pct": round(GLOBAL_WEATHER["humidity"] + random.uniform(-1.0, 1.0), 1),
                        "heat_loss_w": round(noisy_loss, 1),
                        "severity": severity_from_w(noisy_loss),
                        "is_hardware": False,
                        "lon": b["lon"],
                        "lat": b["lat"],
                        "timestamp": time.time(),
                        "is_anomaly": False,
                        "anomaly_reason": None
                    }
                    
                    # Update local nodes registry
                    NODE_REGISTRY[b["node_id"]] = reading
                    
                    # Broadcast telemetry packet
                    dead = []
                    for ws in WS_CLIENTS:
                        try:
                            await ws.send_json({"type": "telemetry", "data": reading})
                        except Exception:
                            dead.append(ws)
                    
                    for ws in dead:
                        if ws in WS_CLIENTS:
                            WS_CLIENTS.remove(ws)
            
        except Exception as e:
            print(f"WebSocket Physics Streamer loop error: {e}")
            
        await asyncio.sleep(1.0)
