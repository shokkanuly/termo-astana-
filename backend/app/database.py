import os
import time
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5435/termo_astana")

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        for i in range(15):
            try:
                _pool = psycopg2.pool.ThreadedConnectionPool(1, 20, DATABASE_URL)
                print("Successfully established database connection pool.")
                break
            except Exception as e:
                print(f"Database connection failed: {e}. Retrying ({i+1}/15) in 2 seconds...")
                time.sleep(2)
        if _pool is None:
            raise Exception("Failed to connect to the database. Verify that Docker container is running on port 5435.")
    return _pool

@contextmanager
def get_db():
    p = get_pool()
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
    print("Initializing database extensions and tables...")
    with get_db() as conn:
        with conn.cursor() as cur:
            # 1. Enable Spatial and Time-series extensions
            cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
            
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
            
            # Create GIST spatial index for fast intersects/bounding box queries
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
            
            # Convert telemetry table into a TimescaleDB hypertable on the 'time' column
            try:
                cur.execute("SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);")
                print("TimescaleDB hypertable 'telemetry' is ready.")
            except Exception as e:
                # Catch if it's already a hypertable
                print(f"Hypertable creation info: {e}")
                
            cur.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_building_time ON telemetry (building_id, time DESC);")
            
    print("Database schemas initialized.")
