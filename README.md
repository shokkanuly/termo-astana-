# TermoAstana (Digital Thermal Twin)

TermoAstana is a digital thermal twin application for the city of Astana. It gathers real-time heat loss telemetry, maps building insulation performance, and simulates district-wide waste metrics to prioritize thermal upgrades.

## Features

- **Live Telemetry & Dashboard**:
  - Monitors facade temperature, ambient temperature, humidity, and heat loss.
  - Features real-time WebSocket communication to broadcast live sensor readings from edge nodes.
  - Displays virtual node status, system coverages, and peak metrics.
- **Interactive Astana Map**:
  - Renders building positions, roads, river paths, and district overlays (Esil, Saryarka, Almaty, Baikonyr, Sarayshyk) with heat intensity values.
- **Dynamic Building Analysis & ROI Calculator**:
  - Calculates building heat loss (kW) based on material layers (e.g. brick, modern insulation, khrushchyovka standard) and outside ambient temperature.
  - Models the return on investment (ROI) of thermal renovation packages, showing the amortized costs over a 5-year period.
- **IoT Edge Emulator**:
  - A standalone script (`simulator/iot_emulator.py`) simulating up to 100 virtual nodes (and hardware prototype ESP32 anchors) broadcasting telemetry packages to the backend.

## Directory Structure

```text
termo astana/
├── backend/               # FastAPI python backend
│   ├── main.py            # Uvicorn bootstrapper (port 8000)
│   ├── requirements.txt   # Python dependency list
│   ├── app/
│   │   ├── buildings_db.py  # Mock database of Astana structures & materials
│   │   ├── city_map.py      # Map dimensions, geometry paths, and coordinates
│   │   ├── main.py          # FastAPI server, REST routes, and WebSocket endpoints
│   │   ├── schemas.py       # Pydantic schemas for request/response validation
│   │   └── thermal_engine.py # Math formula solver (heat loss, ROI, waste cost)
│   └── simulator/
│       └── iot_emulator.py  # WebSocket simulation client to mimic ESP32 edge sensors
└── frontend/              # Web dashboard frontend
    ├── index.html         # Live thermal twin dashboard view
    ├── css/               # Core design styles
    └── js/                # WebSocket client, SVG map canvas renderer, and UI controllers
```

## Tech Stack

- **Backend**: Python 3, FastAPI, Uvicorn, Websockets
- **Simulator**: Python asyncio, websockets
- **Frontend**: Vanilla HTML5, SVG canvas mapping, CSS3, Vanilla JavaScript

## Setup & Running Locally

### 1. Launch the FastAPI Backend
```bash
cd "termo astana/backend"

# Create a virtual environment and activate it
python3 -m venv .venv
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Start backend server (runs on port 8000)
python main.py
```

### 2. Launch the IoT Simulator
In a separate terminal (with the virtual environment active):
```bash
cd "termo astana/backend"
source .venv/bin/activate

# Run emulator (streams mock telemetry from 100 virtual nodes to backend)
python simulator/iot_emulator.py
```

### 3. Open the Frontend
Since static files are mounted on the same host inside the FastAPI server, you can view the fully responsive map dashboard by navigating to:
`http://127.0.0.1:8000`
