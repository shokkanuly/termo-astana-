import os
import time
import sqlite3
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5435/termo_astana")
SQLITE_PATH = os.getenv("SQLITE_PATH", "termo_astana.db")

DB_BACKEND = "postgres"  # Will fallback to "sqlite" if postgres is offline
_pool = None

def get_pool():
    global _pool, DB_BACKEND
    if DB_BACKEND == "sqlite":
        return None
    if _pool is None:
        # Import psycopg2 only when needed, to allow sqlite running without it if necessary
        try:
            import psycopg2
            from psycopg2 import pool
            _pool = psycopg2.pool.ThreadedConnectionPool(1, 20, DATABASE_URL, connect_timeout=2)
            print("Successfully established database connection pool for PostgreSQL.")
        except Exception as e:
            print(f"PostgreSQL connection failed: {e}. Falling back to SQLite.")
            DB_BACKEND = "sqlite"
    return _pool

@contextmanager
def get_db():
    global DB_BACKEND
    p = get_pool()
    if DB_BACKEND == "sqlite":
        conn = sqlite3.connect(SQLITE_PATH)
        # Enable write-ahead logging (WAL) for concurrency
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            pass
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = p.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            p.putconn(conn)

def init_db():
    global DB_BACKEND
    print("Initializing database extensions and tables...")
    
    # Check/establish pool to determine backend
    get_pool()
    
    if DB_BACKEND == "sqlite":
        print(f"Initializing SQLite database at {SQLITE_PATH}...")
        with get_db() as conn:
            cur = conn.cursor()
            
            # Create buildings table (No PostGIS in SQLite, we will store coordinate arrays or fallback geometries in RAM/DB)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS buildings (
                    id TEXT PRIMARY KEY,
                    osm_id TEXT,
                    height REAL NOT NULL DEFAULT 15.0,
                    material TEXT NOT NULL,
                    address TEXT NOT NULL,
                    district TEXT NOT NULL,
                    facade_area_m2 REAL NOT NULL DEFAULT 1000.0,
                    roof_area_m2 REAL NOT NULL DEFAULT 500.0,
                    window_area_m2 REAL NOT NULL DEFAULT 200.0,
                    geom_geojson TEXT
                );
            """)
            
            # Create telemetry table for building thermal time-series
            cur.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    time TEXT NOT NULL,
                    building_id TEXT NOT NULL,
                    temp_in REAL NOT NULL,
                    temp_out REAL NOT NULL,
                    heat_loss REAL NOT NULL,
                    is_anomaly INTEGER DEFAULT 0,
                    anomaly_reason TEXT
                );
            """)
            
            # Create traffic telemetry log table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS traffic_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    district_id TEXT,
                    traffic_speed REAL,
                    congestion_index REAL,
                    co2_ppm REAL,
                    heat_loss_wm2 REAL,
                    ambient_temp_c REAL,
                    is_anomaly INTEGER DEFAULT 0,
                    anomaly_score REAL DEFAULT 0.0,
                    source TEXT DEFAULT 'twin'
                );
            """)
            
            # Create thermographic upgrades audit log table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS thermo_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    building_id TEXT,
                    building_name TEXT,
                    construction_year INTEGER,
                    base_heat_loss_wm2 REAL,
                    insulation_type TEXT,
                    insulation_thickness_mm INTEGER,
                    reduction_percent INTEGER,
                    annual_co2_tons REAL,
                    annual_savings_kzt INTEGER,
                    ai_analysis TEXT,
                    ai_recommendations TEXT
                );
            """)
            
            # Create control events log table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS control_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    district_id TEXT,
                    mode TEXT,
                    risk_level TEXT,
                    signal_phase TEXT,
                    power_state TEXT,
                    power_usage_kw REAL,
                    reason TEXT,
                    action_json TEXT
                );
            """)
            
            # Create AI chat history table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT NOT NULL DEFAULT 'default',
                    mode TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT
                );
            """)
            
        print("SQLite schemas initialized successfully.")
    else:
        print("Initializing PostgreSQL/PostGIS database...")
        with get_db() as conn:
            with conn.cursor() as cur:
                # 1. Enable Spatial and Time-series extensions
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
                    cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
                except Exception as e:
                    print(f"Warning: Could not initialize extensions: {e}")
                
                # 2. Create buildings table with PostGIS geometry (SRID 4326)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS buildings (
                        id VARCHAR(50) PRIMARY KEY,
                        osm_id VARCHAR(50),
                        height DOUBLE PRECISION NOT NULL DEFAULT 15.0,
                        material VARCHAR(100) NOT NULL,
                        address VARCHAR(255) NOT NULL,
                        district VARCHAR(100) NOT NULL,
                        facade_area_m2 DOUBLE PRECISION NOT NULL DEFAULT 1000.0,
                        roof_area_m2 DOUBLE PRECISION NOT NULL DEFAULT 500.0,
                        window_area_m2 DOUBLE PRECISION NOT NULL DEFAULT 200.0,
                        geom GEOMETRY(Polygon, 4326) NOT NULL
                    );
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_buildings_geom ON buildings USING GIST (geom);")
                
                # 3. Create telemetry table for time-series logging
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry (
                        time TIMESTAMPTZ NOT NULL,
                        building_id VARCHAR(50) NOT NULL,
                        temp_in DOUBLE PRECISION NOT NULL,
                        temp_out DOUBLE PRECISION NOT NULL,
                        heat_loss DOUBLE PRECISION NOT NULL,
                        is_anomaly BOOLEAN DEFAULT FALSE,
                        anomaly_reason VARCHAR(255)
                    );
                """)
                try:
                    cur.execute("SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);")
                except Exception as e:
                    print(f"Hypertable creation info: {e}")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_building_time ON telemetry (building_id, time DESC);")
                
                # 4. Create traffic telemetry log table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS traffic_logs (
                        id SERIAL,
                        ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        district_id TEXT,
                        traffic_speed REAL,
                        congestion_index REAL,
                        co2_ppm REAL,
                        heat_loss_wm2 REAL,
                        ambient_temp_c REAL,
                        is_anomaly INTEGER DEFAULT 0,
                        anomaly_score REAL DEFAULT 0.0,
                        source TEXT DEFAULT 'twin',
                        PRIMARY KEY (id, ts)
                    );
                """)
                try:
                    cur.execute("SELECT create_hypertable('traffic_logs', 'ts', if_not_exists => TRUE);")
                except Exception as e:
                    print(f"Hypertable traffic_logs info: {e}")
                
                # 5. Create thermographic upgrades audit log table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS thermo_logs (
                        id SERIAL PRIMARY KEY,
                        ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        building_id TEXT,
                        building_name TEXT,
                        construction_year INTEGER,
                        base_heat_loss_wm2 REAL,
                        insulation_type TEXT,
                        insulation_thickness_mm INTEGER,
                        reduction_percent INTEGER,
                        annual_co2_tons REAL,
                        annual_savings_kzt INTEGER,
                        ai_analysis TEXT,
                        ai_recommendations TEXT
                    );
                """)
                
                # 6. Create control events log table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS control_events (
                        id SERIAL PRIMARY KEY,
                        ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        district_id TEXT,
                        mode TEXT,
                        risk_level TEXT,
                        signal_phase TEXT,
                        power_state TEXT,
                        power_usage_kw REAL,
                        reason TEXT,
                        action_json TEXT
                    );
                """)
                
                # 7. Create AI chat history table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id SERIAL PRIMARY KEY,
                        ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        session_id TEXT NOT NULL DEFAULT 'default',
                        mode TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        context TEXT
                    );
                """)
        print("PostgreSQL database schemas initialized.")

