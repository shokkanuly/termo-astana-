"""Log history, database statistics, runtime config and the traffic forecast."""

import os

import numpy as np
import pandas as pd
from fastapi import APIRouter

from app import repository as repo
from app.database import get_db, is_sqlite
from app.utils import run_db

router = APIRouter()

# ─────────────────────────────────────────────
# REST ENDPOINTS - HISTORY & LOG READERS
# ─────────────────────────────────────────────
@router.get("/api/history/traffic")
async def get_traffic_history(limit: int = 50):
    records = await run_db(repo.fetch_traffic_history, limit)
    return {"records": records, "count": len(records)}

@router.get("/api/history/thermo")
async def get_thermo_history(limit: int = 30):
    records = await run_db(repo.fetch_thermo_history, limit)
    return {"records": records, "count": len(records)}

@router.get("/api/history/chat")
async def get_chat_history(session_id: str = "default", mode: str = "traffic", limit: int = 30):
    records = await run_db(repo.fetch_chat_history, session_id, mode, limit)
    return {"records": records, "session_id": session_id, "mode": mode}

@router.get("/api/history/control")
async def get_control_history(limit: int = 30):
    records = await run_db(repo.fetch_control_history, limit)
    return {"records": records, "count": len(records)}

@router.get("/api/db/stats")
async def get_db_stats():
    stats = await run_db(repo.fetch_db_stats)
    return stats

@router.get("/api/config")
async def get_config():
    return {"gemini_active": bool(os.getenv("GEMINI_API_KEY"))}

@router.get("/api/forecast")
async def get_forecast():
    conn = get_db().__enter__()
    try:
        if is_sqlite():
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
