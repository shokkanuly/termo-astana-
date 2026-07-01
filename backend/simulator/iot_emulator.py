#!/usr/bin/env python3
"""
TermoAstana IoT Edge Emulator (v3.0)

Simulates 99 virtual sensor nodes across Astana districts in WGS84 coordinates.
Streams real-time telemetry packets to the FastAPI backend via WebSocket.

Usage:
    python simulator/iot_emulator.py
    python simulator/iot_emulator.py --nodes 99 --interval 2
"""

import argparse
import asyncio
import json
import math
import random
import time

try:
    import websockets
except ImportError:
    print("Install websockets first: pip install websockets")
    raise

DEFAULT_PORT = 8000

MATERIAL_R_MAPPING = {
    "modern_ventilated": 3.0,
    "glass_curtain": 1.2,
    "brick_soviet": 0.8,
    "brezhnevka_panel": 0.7,
    "khrushchyovka_panel": 0.4
}

def severity_from_w(w: float) -> str:
    if w >= 200000:
        return "CRITICAL"
    if w >= 100000:
        return "HIGH"
    if w >= 50000:
        return "MODERATE"
    return "LOW"

def generate_nodes(count: int, include_hardware: bool) -> list:
    nodes = []
    
    # Yesil/Saryarka center anchors
    lat_center, lon_center = 51.1283, 71.4305

    if include_hardware:
        nodes.append({
            "node_id": "esp32_hw_01",
            "district": "Сарыарка",
            "address": "ул. Сейфуллина, 24 [PROTOTYPE]",
            "material": "khrushchyovka_panel",
            "facade_area": 1500.0,
            "is_hardware": True,
            "phase": 0.0,
            "lon": 71.4285,
            "lat": 51.1285,
        })

    for i in range(count):
        # Coordinates in Esil/Yesil area
        lat = lat_center + random.uniform(-0.007, 0.007)
        lon = lon_center + random.uniform(-0.015, 0.015)
        material = random.choice(list(MATERIAL_R_MAPPING.keys()))
        nodes.append({
            "node_id": f"VIRT-{i+1:03d}",
            "district": "Есиль",
            "address": f"ул. Достык, {random.randint(1, 100)}",
            "material": material,
            "facade_area": random.uniform(800.0, 4500.0),
            "is_hardware": False,
            "phase": random.uniform(0.0, 2.0 * math.pi),
            "lon": lon,
            "lat": lat,
        })
    return nodes

def simulate_reading(node: dict, t: float, outside_temp: float) -> dict:
    r_total = MATERIAL_R_MAPPING[node["material"]]
    area = node["facade_area"]

    # Daily temp variation
    daily_variation = math.sin(t / 20.0 + node["phase"]) * 2.0
    ambient = outside_temp + daily_variation + random.gauss(0, 0.4)
    
    # Calculate facade temp (approx. 80% indoor influence + ambient)
    facade_temp = ambient + (22.0 - ambient) * (0.12 + random.uniform(0.02, 0.08))
    humidity = random.uniform(40.0, 70.0)

    delta_t = 22.0 - ambient
    heat_loss_w = (area * delta_t) / r_total * random.uniform(0.95, 1.05)
    heat_loss_w = max(heat_loss_w, 0.0)

    return {
        "node_id": node["node_id"],
        "district": node["district"],
        "address": node["address"],
        "temp_facade_c": round(facade_temp, 1),
        "temp_ambient_c": round(ambient, 1),
        "humidity_pct": round(humidity, 1),
        "heat_loss_w": round(heat_loss_w, 1),
        "severity": severity_from_w(heat_loss_w),
        "is_hardware": node["is_hardware"],
        "lon": round(node["lon"], 6),
        "lat": round(node["lat"], 6),
        "timestamp": time.time(),
    }

async def run_emulator(node_count: int, interval: float, include_hardware: bool, port: int):
    ws_url = f"ws://127.0.0.1:{port}/ws/telemetry"
    nodes = generate_nodes(node_count, include_hardware)
    outside_temp = -15.0
    tick = 0

    print("TermoAstana IoT Emulator (v3.0 WGS84)")
    print(f"  Nodes: {len(nodes)} ({sum(1 for n in nodes if n['is_hardware'])} hardware)")
    print(f"  Target: {ws_url}")
    print(f"  Interval: {interval}s\n")

    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                print(f"[{time.strftime('%H:%M:%S')}] Connected to backend WebSocket")
                init = await ws.recv()
                
                while True:
                    tick += 1
                    # Fluctuating outside temperature
                    outside_temp = -15.0 + math.sin(tick / 50.0) * 5.0

                    batch = [simulate_reading(n, tick, outside_temp) for n in nodes]
                    for reading in batch:
                        await ws.send(json.dumps({
                            "type": "sensor_reading",
                            "data": reading,
                        }))

                    if tick % 5 == 0:
                        critical = sum(1 for r in batch if r["severity"] == "CRITICAL")
                        print(
                            f"  tick={tick} outside={outside_temp:.1f}°C "
                            f"nodes={len(batch)} critical={critical}"
                        )

                    await asyncio.sleep(interval)

        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError, OSError) as e:
            print(f"[{time.strftime('%H:%M:%S')}] Disconnected ({e}). Retrying in 3s...")
            await asyncio.sleep(3)

def main():
    parser = argparse.ArgumentParser(description="TermoAstana IoT Edge Emulator")
    parser.add_argument("--nodes", type=int, default=99, help="Virtual node count")
    parser.add_argument("--interval", type=float, default=2.0, help="Interval in seconds")
    parser.add_argument("--hardware", action="store_true", help="Include reference ESP32 node")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Backend port")
    args = parser.parse_args()

    asyncio.run(run_emulator(args.nodes, args.interval, args.hardware, args.port))

if __name__ == "__main__":
    main()
