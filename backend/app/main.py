"""Astana Twin unified API — application shell.

Builds the FastAPI app, wires middleware and lifespan, and mounts the domain routers.
Endpoint logic lives under app/routers/; the physics, control and data layers live in
their own modules alongside.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import get_db, init_db
from app.osm_ingest import ingest_data
from app.weather_worker import weather_polling_worker
from app.websocket_server import websocket_streamer
from app.routers import ai, buildings, control, history, ws

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
logger = logging.getLogger("AstanaTwinCombinedAPI")

# ─────────────────────────────────────────────
# FASTAPI LIFESPAN
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize tables (PostgreSQL or SQLite fallback)
    init_db()
    
    # 2. Automatically ingest OSM buildings if empty
    try:
        count = 0
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM buildings;")
            count = cur.fetchone()[0]
                
        if count <= 1:
            print("Buildings database is empty. Running OpenStreetMap ingestion...")
            ingest_data()
        else:
            print(f"Database contains {count} buildings. Skipping ingestion.")
    except Exception as e:
        print(f"Failed to check/ingest buildings: {e}")
        
    # 3. Start background simulation workers
    asyncio.create_task(weather_polling_worker())
    asyncio.create_task(websocket_streamer())
        
    yield

# ─────────────────────────────────────────────
# APP DEFINITION
# ─────────────────────────────────────────────
app = FastAPI(
    title="Astana Twin Unified API", 
    version="4.0", 
    description="Combined Digital Thermal Twin & Traffic Management platform for Astana, Kazakhstan",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# ROUTERS
# ─────────────────────────────────────────────
app.include_router(buildings.router)
app.include_router(control.router)
app.include_router(ai.router)
app.include_router(history.router)
app.include_router(ws.router)

# ─────────────────────────────────────────────
# STATIC FILE SERVING
# ─────────────────────────────────────────────
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
else:
    _frontend = Path(__file__).resolve().parent.parent.parent / "frontend"
    if _frontend.is_dir():
         app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
