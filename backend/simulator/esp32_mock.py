import time
import requests
import random
import argparse

def run_mock(port):
    api_url = f"http://127.0.0.1:{port}/api/v1/esp32/telemetry"
    print("Starting ESP32 Microcontroller Hardware Mock Simulation...")
    print(f"Target Endpoint: {api_url}")
    print("Press Ctrl+C to terminate.")
    
    t_in = 22.0
    t_out = -15.0
    window_open = False
    tick = 0
    
    while True:
        tick += 1
        
        # Every 10 ticks (~50s), toggle window open/closed to simulate real event
        if tick % 10 == 0:
            window_open = not window_open
            print(f"\n[EVENT] WINDOW STATUS TOGGLED: open={window_open}\n")
            
        # Physical model simulation
        if window_open:
            # Temperature falls rapidly when window opens
            t_in -= random.uniform(0.3, 0.7)
            t_in = max(t_in, 8.5)
        else:
            # Recover back to room temperature when window closes
            if t_in < 21.5:
                t_in += random.uniform(0.2, 0.5)
            else:
                t_in += random.uniform(-0.1, 0.1)
                
        # Outside temp fluctuates slightly
        t_out += random.uniform(-0.1, 0.1)
        
        payload = {
            "node_id": "esp32_hw_01",
            "t_in": round(t_in, 1),
            "t_out": round(t_out, 1),
            "window_open": window_open,
            "humidity": round(random.uniform(45.0, 55.0), 1)
        }
        
        try:
            r = requests.post(api_url, json=payload, timeout=3)
            r.raise_for_status()
            res = r.json()
            anomaly_alert = "🚨 ANOMALY ALERT!" if res.get("anomaly") else "🟢 NORMAL"
            print(
                f"[{time.strftime('%H:%M:%S')}] POST -> t_in={payload['t_in']}°C "
                f"t_out={payload['t_out']}°C window={payload['window_open']} | "
                f"Response: {anomaly_alert} ({res.get('reason', 'no reason')})"
            )
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Telemetry POST failed: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ESP32 Mock Client")
    parser.add_argument("--port", type=int, default=8000, help="FastAPI port")
    args = parser.parse_args()
    run_mock(args.port)
