import time
import requests
import random
from datetime import datetime

URL = "http://localhost:8008/api/telemetry"
NODE_ID = "ESP32-NODE-ASTANA-01"

print(f"Mock ESP32 Edge Transmitter active. Posting to {URL} every 2.5 seconds...")

# Start parameters
temp_c = 21.0
distance_cm = 65.0
power_kw = 3.4

try:
    while True:
        # Simulate slight variations
        temp_c = max(15.0, min(35.0, temp_c + random.uniform(-0.5, 0.5)))
        distance_cm = max(2.0, min(150.0, distance_cm + random.uniform(-5.0, 5.0)))
        power_kw = max(1.2, min(10.5, power_kw + random.uniform(-0.35, 0.45)))
        
        # Calculate mock speed based on proximity loop trigger
        if distance_cm < 15.0:
            flow_speed_kmh = round(random.uniform(5.0, 15.0), 1)
            lane_blocked = True
        else:
            flow_speed_kmh = round(random.uniform(45.0, 65.0), 1)
            lane_blocked = False
            
        payload = {
            "node_id": NODE_ID,
            "temp_c": round(temp_c, 1),
            "distance_cm": round(distance_cm, 1),
            "flow_speed_kmh": flow_speed_kmh,
            "lane_blocked": lane_blocked,
            "power_kw": round(power_kw + (1.8 if lane_blocked else 0.0), 2)
        }
        
        try:
            r = requests.post(URL, json=payload, timeout=2.0)
            if r.status_code == 200:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Uploaded payload: Temp={payload['temp_c']}°C, Dist={payload['distance_cm']}cm, Speed={payload['flow_speed_kmh']}km/h, Power={payload['power_kw']}kW")
            else:
                print(f"Server returned HTTP {r.status_code}")
        except Exception as e:
            print(f"Connection error: {e}. FastAPI server might be offline.")
            
        time.sleep(2.5)

except KeyboardInterrupt:
    print("\nMock ESP32 Transmitter stopped by user.")
