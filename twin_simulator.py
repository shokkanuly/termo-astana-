import time
import requests
import random
from datetime import datetime

URL = "http://localhost:8008/api/twin/telemetry"
DISTRICT_ID = "nurzhol_sector_A"

print(f"Astana Twin Simulator active. Posting to {URL} once per second...")

# Baseline metrics
traffic_speed = 52.0
congestion = 30.0
co2_ppm = 410.0
heat_loss = 95.0
ambient_temp = 30.0

event_timer = 0
is_anomaly_active = False

try:
    while True:
        event_timer += 1
        
        # Trigger an anomaly event every 30 seconds, lasting for 10 seconds
        if event_timer % 30 == 0:
            is_anomaly_active = True
            print("\n[SIMULATOR ALERT] Triggering Traffic & CO2 Congestion Anomaly!")
        elif event_timer % 30 == 10:
            is_anomaly_active = False
            print("\n[SIMULATOR INFO] Resolving anomaly, returning to nominal operations.")
            
        # Calculate dynamic fluctuations
        if is_anomaly_active:
            # Traffic slowdown, high congestion, air quality degradation
            traffic_speed = max(8.0, traffic_speed - random.uniform(5.0, 10.0))
            congestion = min(95.0, congestion + random.uniform(8.0, 15.0))
            co2_ppm = min(980.0, co2_ppm + random.uniform(50.0, 100.0))
            heat_loss = min(180.0, heat_loss + random.uniform(3.0, 8.0))
            ai_trigger = True
        else:
            # Return to normal parameters
            traffic_speed = min(58.0, max(42.0, traffic_speed + random.uniform(-2.0, 2.0) if traffic_speed > 30 else traffic_speed + 5.0))
            congestion = max(20.0, min(45.0, congestion + random.uniform(-3.0, 3.0) if congestion < 60 else congestion - 5.0))
            co2_ppm = max(390.0, min(480.0, co2_ppm + random.uniform(-10.0, 10.0) if co2_ppm < 600 else co2_ppm - 40.0))
            heat_loss = max(70.0, min(120.0, heat_loss + random.uniform(-2.0, 2.0) if heat_loss < 140 else heat_loss - 5.0))
            ai_trigger = False
            
        ambient_temp = max(28.0, min(33.0, ambient_temp + random.uniform(-0.3, 0.3)))
        
        # Build JSON payload
        payload = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "district_id": DISTRICT_ID,
            "metrics": {
                "traffic_speed_kmh": round(traffic_speed, 1),
                "congestion_index": round(congestion, 1),
                "air_quality_co2_ppm": round(co2_ppm, 1),
                "facade_heat_loss_w_m2": round(heat_loss, 1),
                "ambient_temp_c": round(ambient_temp, 1)
            },
            "ai_trigger": ai_trigger
        }
        
        try:
            response = requests.post(URL, json=payload, timeout=2.0)
            if response.status_code == 200:
                print(f"[{payload['timestamp']}] Post successful: Speed={payload['metrics']['traffic_speed_kmh']}km/h, CO2={payload['metrics']['air_quality_co2_ppm']}ppm, Trigger={ai_trigger}")
            else:
                print(f"[{payload['timestamp']}] Warning: Server returned HTTP {response.status_code}")
        except Exception as e:
            print(f"Connection error: {e}. FastAPI server might be offline.")
            
        time.sleep(1.0)
        
except KeyboardInterrupt:
    print("\nSimulator stopped by user.")
