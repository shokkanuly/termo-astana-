import requests
import time

# Simple in-memory cache for Astana weather
_weather_cache = {
    "data": None,
    "expiry": 0
}

def get_astana_weather():
    """Fetches real-time weather metrics for Astana (Esil district) from Open-Meteo API with a 10-minute cache."""
    global _weather_cache
    now = time.time()
    
    # Return cached data if valid
    if _weather_cache["data"] and now < _weather_cache["expiry"]:
        return _weather_cache["data"]
        
    url = "https://api.open-meteo.com/v1/forecast?latitude=51.1283&longitude=71.4305&current=temperature_2m,relative_humidity_2m,wind_speed_10m"
    try:
        res = requests.get(url, timeout=3)
        res.raise_for_status()
        current = res.json().get("current", {})
        
        # Wind speed in open-meteo is km/h by default. Convert to m/s.
        wind_kmh = current.get("wind_speed_10m", 12.6)
        wind_ms = round(wind_kmh / 3.6, 1)
        
        data = {
            "temp_out": current.get("temperature_2m", -15.0),
            "humidity": current.get("relative_humidity_2m", 65.0),
            "wind_speed": wind_ms
        }
        _weather_cache["data"] = data
        _weather_cache["expiry"] = now + 600  # 10 minutes cache
        return data
    except Exception as e:
        print(f"Weather API failed ({e}). Falling back to cached or typical winter conditions.")
        if _weather_cache["data"]:
            return _weather_cache["data"]
        return {
            "temp_out": -15.0,
            "humidity": 70.0,
            "wind_speed": 4.5
        }
