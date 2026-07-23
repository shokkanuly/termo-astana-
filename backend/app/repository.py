"""Query layer for the log tables.

Connections, schema and backend selection live in ``database.py``; this module owns the
reads and writes on top of them.

``DB_BACKEND`` is resolved per call rather than imported once, because ``database`` flips it
to ``"sqlite"`` during ``init_db()`` — a module-level copy taken at import time would still
say ``"postgres"`` and emit the wrong placeholder style.
"""

import json

import pandas as pd

import app.database as db_mod
from app.database import get_db


def _is_sqlite() -> bool:
    return db_mod.DB_BACKEND == "sqlite"


def _placeholder() -> str:
    return "?" if _is_sqlite() else "%s"


def _read_sql(sql: str, params=None) -> pd.DataFrame:
    """Run a query and normalise the ``ts`` column to an ISO-8601 Z string."""
    with get_db() as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"]).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df


# ─────────────────────────────────────────────
# WRITERS
# ─────────────────────────────────────────────
def save_traffic_log(row: dict):
    with get_db() as conn:
        cur = conn.cursor()
        if _is_sqlite():
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


def save_thermo_log(row: dict):
    with get_db() as conn:
        cur = conn.cursor()
        if _is_sqlite():
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


def save_chat_message(session_id: str, mode: str, role: str, content: str, context: dict):
    with get_db() as conn:
        cur = conn.cursor()
        p = _placeholder()
        cur.execute(f"""
            INSERT INTO chat_history (session_id, mode, role, content, context)
            VALUES ({p}, {p}, {p}, {p}, {p})
        """, (session_id, mode, role, content, json.dumps(context)))


def save_control_event(row: dict):
    with get_db() as conn:
        cur = conn.cursor()
        if _is_sqlite():
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


# ─────────────────────────────────────────────
# READERS
# ─────────────────────────────────────────────
def fetch_traffic_history(limit: int = 50) -> list:
    df = _read_sql(
        f"SELECT * FROM traffic_logs ORDER BY id DESC LIMIT {_placeholder()}",
        params=(limit,),
    )
    return df.to_dict(orient="records")


def fetch_thermo_history(limit: int = 50) -> list:
    df = _read_sql(
        f"SELECT * FROM thermo_logs ORDER BY id DESC LIMIT {_placeholder()}",
        params=(limit,),
    )
    return df.to_dict(orient="records")


def fetch_chat_history(session_id: str, mode: str, limit: int = 30) -> list:
    p = _placeholder()
    df = _read_sql(f"""
        SELECT id, ts, role, content, context
        FROM chat_history
        WHERE session_id = {p} AND mode = {p}
        ORDER BY id DESC LIMIT {p}
    """, params=(session_id, mode, limit))
    # Reversed so the caller receives the conversation oldest-first.
    return df.iloc[::-1].to_dict(orient="records")


def fetch_control_history(limit: int = 30) -> list:
    df = _read_sql(
        f"SELECT * FROM control_events ORDER BY id DESC LIMIT {_placeholder()}",
        params=(limit,),
    )
    return df.to_dict(orient="records")


def fetch_db_stats() -> dict:
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
