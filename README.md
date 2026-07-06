# TermoAstana — Digital Thermal Twin

TermoAstana is a high-performance Digital Thermal Twin application for the city of Astana. It implements spatial analytics, physics-based simulations, and live telemetry to monitor building insulation performance, identify heat loss anomalies, and model the financial feasibility of insulation upgrades at city-wide scale.

---

## 🚀 Key Features

* **3D Building Extrusion Map**: Renders real-world 3D building models color-coded by thermal energy loss intensity (Green $\rightarrow$ Orange $\rightarrow$ Red) built using MapLibre GL and React.
* **Dynamic Bounding Box (BBOX) Loading**: Scaled to support the entire city of Astana (15,000+ buildings). Leverages PostGIS indexes (`ST_MakeEnvelope`, `ST_Intersects`) and fetches geometry bounds dynamically only when panning/zooming stops (`onMoveEnd`), capping payload sizes to keep client/server memory footprints stable.
* **Performance Zoom Gating**: Automatically hides 3D building rendering and pauses API polling when zoomed out (`zoom < 14`), displaying a glowing warning HUD overlays: `⚠️ Zoom in to load thermal polygons`.
* **Physics-Based Interpolation Engine**: Dropped mock hardware generators in favor of a native ASGI-based simulation loop:
  - **Astana Weather Worker**: Polling routine running every 15 minutes to cache current temperature and wind speed for Astana from the Open-Meteo API.
  - **SNiP (СНиП) Thermal Equations**: Calculates baseline heat loss using building geometry facade areas and material resistance coefficients:
    $$\text{Heat Loss (W)} = \frac{\text{Facade Area}}{\text{Thermal Resistance (R)}} \times (21.0 - T_{\text{out}})$$
  - **Gaussian Fluctuation Stream**: Streams telemetry packets every 1 second over WebSockets, applying a $2\%$ Gaussian standard deviation noise to simulate smart meter sensor fluctuation.
* **Interactive Polygon Drill-Down**: Click on any building footprint on the map to display its glowing neon-cyan border outline and instantly populate its thermal passport sheet (address, height, window ratio, insulation upgrade ROI curve, and 24h consumption charts).

---

## 📂 Project Architecture

```text
termo-astana/
├── backend/                  # FastAPI Backend Application
│   ├── main.py               # Uvicorn entry point & WebSocket server (port 8008)
│   ├── requirements.txt      # Python backend dependencies
│   ├── app/
│   │   ├── database.py       # PostGIS database pool & TimescaleDB schema manager
│   │   ├── osm_ingest.py     # Grid partition Overpass API downloader & PostGIS parser
│   │   ├── thermal_engine.py # SNiP physics equations & database simulator queries
│   │   ├── weather.py        # Open-Meteo API client with a 10-minute cache
│   │   ├── weather_worker.py # Background asyncio weather poller task
│   │   └── websocket_server.py # 1-second WebSocket telemetry broadcast loops
│   └── simulator/            # Archive emulator scripts (Deprecated)
└── frontend/                 # React + Vite Client Dashboard
    ├── index.html            # Main HTML wrapper
    ├── src/
    │   ├── main.jsx          # React app mounter
    │   ├── App.jsx           # Dashboard layout, state machine, and data coordination
    │   ├── MapComponent.jsx  # MapLibre GL 3D wrapper with selection outline handlers
    │   ├── App.css           # Styling rules (industrial dark theme, HUD overlays, warnings)
    │   └── index.css         # Global browser resetting
    └── vite.config.js        # Port proxies for dev redirecting
```

---

## 🛠️ Technology Stack

* **Database**: TimescaleDB + PostGIS 3 (running via Docker on Port `5435`)
* **Backend**: Python 3.11, FastAPI, Uvicorn, Websockets, psycopg2
* **Frontend**: React 18, Vite, MapLibre GL, Recharts, Lucide Icons, Vanilla CSS3

---

## 💻 Local Setup & Development

### 1. Database Setup (Docker Compose)
Launch the PostGIS container:
```bash
docker compose up -d
```
The database will automatically initialize its schema and extensions.

### 2. FastAPI Backend Setup
```bash
cd backend

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Start backend server (runs on http://127.0.0.1:8008)
python main.py
```
*Note: On first startup, the backend automatically performs a grid-partitioned fetch from Overpass API to ingest Astana's building polygons if the database is empty.*

### 3. Frontend Client Setup
In a separate terminal:
```bash
cd frontend

# Install packages
npm install

# Start Vite dev server (runs on http://localhost:5173/)
npm run dev
```

Open `http://localhost:5173` in your browser to view the Digital Thermal Twin dashboard.
