import asyncio
import time
from app.weather import get_astana_weather

# Global weather state storage
GLOBAL_WEATHER = {
    "temp_out": -15.0,
    "wind_speed": 4.5,
    "humidity": 70.0,
    "last_updated": 0
}

async def weather_polling_worker():
    """
    Background worker that runs every 15 minutes to poll real weather for Astana
    and caches it in the GLOBAL_WEATHER dict.
    """
    print("Weather Polling Worker: Initiated background task.")
    while True:
        try:
            loop = asyncio.get_running_loop()
            weather = await loop.run_in_executor(None, get_astana_weather)
            GLOBAL_WEATHER["temp_out"] = weather.get("temp_out", -15.0)
            GLOBAL_WEATHER["wind_speed"] = weather.get("wind_speed", 4.5)
            GLOBAL_WEATHER["humidity"] = weather.get("humidity", 70.0)
            GLOBAL_WEATHER["last_updated"] = time.time()
            print(f"Weather Polling Worker: Astana weather updated (T_out={GLOBAL_WEATHER['temp_out']}°C, Wind={GLOBAL_WEATHER['wind_speed']} m/s)")
        except Exception as e:
            print(f"Weather Polling Worker error: {e}")
        
        # Poll every 15 minutes (900 seconds)
        await asyncio.sleep(900)
