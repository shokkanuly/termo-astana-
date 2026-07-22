import React, { useState, useEffect } from 'react';
import { 
  Search, Thermometer, Wind, Droplets, MapPin, Building2, ChevronRight, Layers, Navigation, Activity
} from 'lucide-react';
import Header from './components/common/Header';
import MapComponent from './components/map/MapComponent';
import ArcGauge from './components/dashboard/ArcGauge';
import ProgressBarWidget from './components/dashboard/ProgressBarWidget';
import SplineAreaWidget from './components/dashboard/SplineAreaWidget';
import StackedBarWidget from './components/dashboard/StackedBarWidget';
import VarianceBarWidget from './components/dashboard/VarianceBarWidget';
import StatGridWidget from './components/dashboard/StatGridWidget';
import StreetDetailPanel from './components/street/StreetDetailPanel';
import { ASTANA_STREETS } from './constants/astanaData';
import './styles/theme.css';

function App() {
  const [viewMode, setViewMode] = useState("twin"); // 'twin' | 'dashboard' | 'street'
  const [themeMode, setThemeMode] = useState("dark"); // 'dark' | 'light'
  
  const [selectedStreet, setSelectedStreet] = useState(null);
  const [cameraPreset, setCameraPreset] = useState("aerial_3d");

  const [activeBuildingId, setActiveBuildingId] = useState(null);
  const [geoJSONData, setGeoJSONData] = useState(null);
  const [selectedBuilding, setSelectedBuilding] = useState(null);

  const [stats, setStats] = useState({
    total_nodes: 1420,
    hardware_nodes: 380,
    virtual_nodes: 1040,
    outside_temp: -15.0,
    humidity: 60.0,
    wind_speed: 3.5,
    peak_heat_loss_w: 184000.0
  });

  const [activeLeftTab, setActiveLeftTab] = useState("registry"); // "registry" | "streets" | "control"
  const [activeRightTab, setActiveRightTab] = useState("passport"); // "passport" | "chat"
  const [mapMode, setMapMode] = useState("dual"); // "thermal" | "traffic" | "dual"

  const [searchQuery, setSearchQuery] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([
    { role: "assistant", content: "Astana Digital Twin System active. Select any street or building for telemetry analysis." }
  ]);

  const [viewState, setViewState] = useState({
    longitude: 71.4305,
    latitude: 51.1283,
    zoom: 14.5,
    pitch: 55,
    bearing: -20
  });

  // Fetch GeoJSON buildings for entire Astana city or bounds
  const fetchBuildings = async (bounds = null) => {
    let url = `/api/v1/buildings/geojson?min_lon=71.30&min_lat=51.05&max_lon=71.55&max_lat=51.20`;
    if (bounds) {
      const { west, south, east, north } = bounds;
      url = `/api/v1/buildings/geojson?min_lon=${west}&min_lat=${south}&max_lon=${east}&max_lat=${north}`;
    }
    try {
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (data && data.features && data.features.length > 0) {
          setGeoJSONData(data);
        }
      }
    } catch (err) {
      // Fallback is handled inside MapComponent
    }
  };

  useEffect(() => {
    fetchBuildings();
  }, []);

  const handleSelectStreet = (street) => {
    setSelectedStreet(street);
    if (street) setViewMode("street");
    else setViewMode("twin");
  };

  const handleSendMessage = (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userMsg = chatInput;
    setChatMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setChatInput("");

    setTimeout(() => {
      let reply = "Astana Twin Analysis: Sector ";
      if (selectedStreet) {
        reply += `${selectedStreet.nameRu} operating within nominal heat dissipation range. Flow index ${selectedStreet.flowRate}%.`;
      } else {
        reply += "Central District operating under standard SNiP thermal compliance baseline.";
      }
      setChatMessages(prev => [...prev, { role: "assistant", content: reply }]);
    }, 400);
  };

  // GeoJSON Roads GeoJSON builder with multi-point city-spanning polylines
  const roadsGeoJSON = {
    type: 'FeatureCollection',
    features: ASTANA_STREETS.map(r => ({
      type: 'Feature',
      properties: { 
        id: r.id, 
        name: r.nameRu, 
        speed: r.currentSpeed,
        color: r.currentSpeed < 40 ? '#ff2a4b' : r.currentSpeed < 50 ? '#ffaa00' : '#ffffff',
        width: selectedStreet?.id === r.id ? 8 : 5
      },
      geometry: {
        type: 'LineString',
        coordinates: r.path || [[r.x1, r.y1], [r.x2, r.y2]]
      }
    }))
  };

  return (
    <div className={`app-container theme-${themeMode}`}>
      <Header 
        viewMode={viewMode}
        setViewMode={setViewMode}
        themeMode={themeMode}
        setThemeMode={setThemeMode}
        selectedStreet={selectedStreet}
        onSelectStreet={handleSelectStreet}
        cameraPreset={cameraPreset}
        setCameraPreset={setCameraPreset}
      />

      <div className="app-content">
        {/* VIEW MODE 1: 3D CITY MAP TWIN */}
        {viewMode === 'twin' && (
          <div className="twin-layout">
            <aside className="left-panel">
              <div className="panel-tabs">
                <button 
                  className={`p-tab ${activeLeftTab === 'registry' ? 'active' : ''}`}
                  onClick={() => setActiveLeftTab('registry')}
                >
                  Buildings
                </button>
                <button 
                  className={`p-tab ${activeLeftTab === 'streets' ? 'active' : ''}`}
                  onClick={() => setActiveLeftTab('streets')}
                >
                  Streets
                </button>
                <button 
                  className={`p-tab ${activeLeftTab === 'control' ? 'active' : ''}`}
                  onClick={() => setActiveLeftTab('control')}
                >
                  Layers
                </button>
              </div>

              {activeLeftTab === 'registry' && (
                <div className="panel-body">
                  <div className="search-box">
                    <Search size={14} />
                    <input 
                      type="text" 
                      placeholder="Search street or building address..." 
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </div>

                  <div className="weather-hud-box">
                    <div className="hud-row">
                      <span><Thermometer size={13} /> Ambient Temperature:</span>
                      <strong className="text-accent">{stats.outside_temp}°C</strong>
                    </div>
                    <div className="hud-row">
                      <span><Wind size={13} /> Wind Velocity:</span>
                      <span>{stats.wind_speed} m/s</span>
                    </div>
                    <div className="hud-row">
                      <span><Droplets size={13} /> Humidity:</span>
                      <span>{stats.humidity}%</span>
                    </div>
                  </div>

                  <div className="section-title">ASTANA ARTERIAL STREETS</div>
                  <div className="streets-quick-list">
                    {ASTANA_STREETS.map(st => (
                      <div 
                        key={st.id} 
                        className={`street-quick-card ${selectedStreet?.id === st.id ? 'active' : ''}`}
                        onClick={() => handleSelectStreet(st)}
                      >
                        <div className="st-info">
                          <span className="st-name">{st.nameRu}</span>
                          <span className="st-speed">Velocity: {st.currentSpeed} km/h</span>
                        </div>
                        <ChevronRight size={14} className="st-icon" />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {activeLeftTab === 'streets' && (
                <div className="panel-body">
                  <div className="section-title">STREET TELEMETRY INDEX</div>
                  {ASTANA_STREETS.map(st => (
                    <div 
                      key={st.id} 
                      className="street-telemetry-row"
                      onClick={() => handleSelectStreet(st)}
                    >
                      <div className="st-row-left">
                        <span className="st-title">{st.nameRu}</span>
                        <span className="st-sub">Baseline: {st.baseSpeed} km/h</span>
                      </div>
                      <span className="badge-speed-ok">{st.currentSpeed} km/h</span>
                    </div>
                  ))}
                </div>
              )}

              {activeLeftTab === 'control' && (
                <div className="panel-body">
                  <div className="section-title">3D MAP DISPLAY MODES</div>
                  <div className="map-mode-buttons">
                    <button 
                      className={`mode-btn ${mapMode === 'dual' ? 'active' : ''}`}
                      onClick={() => setMapMode('dual')}
                    >
                      Thermal + Traffic Layer
                    </button>
                    <button 
                      className={`mode-btn ${mapMode === 'thermal' ? 'active' : ''}`}
                      onClick={() => setMapMode('thermal')}
                    >
                      Thermal Heat Loss Only
                    </button>
                    <button 
                      className={`mode-btn ${mapMode === 'traffic' ? 'active' : ''}`}
                      onClick={() => setMapMode('traffic')}
                    >
                      Traffic Speed Layer
                    </button>
                  </div>
                </div>
              )}
            </aside>

            <main className="map-wrapper">
              <MapComponent 
                geoJSONData={geoJSONData}
                activeBuildingId={activeBuildingId}
                onSelectBuilding={(id) => setActiveBuildingId(id)}
                onBoundsChange={(bounds) => fetchBuildings(bounds)}
                onViewportChange={(vp) => setViewState(vp)}
                roadsGeoJSON={roadsGeoJSON}
                mapMode={mapMode}
                selectedStreet={selectedStreet}
                onSelectStreet={(st) => handleSelectStreet(st)}
                cameraPreset={cameraPreset}
                theme={themeMode}
              />

              <div className="hud-bottom-bar">
                <ArcGauge title="City Thermal Load" value={11000} maxValue={15000} delta="-4 000" footerText="Astana District Total (kW)" />
                <ArcGauge title="Traffic Flow Index" value={8400} maxValue={10000} delta="+1 200" footerText="Throughput Efficiency (%)" />
                <ArcGauge title="Insulation Ratio" value={6200} maxValue={10000} delta="+450" footerText="Upgraded Facades Score" />
              </div>
            </main>

            <aside className="right-panel">
              <div className="panel-tabs">
                <button 
                  className={`p-tab ${activeRightTab === 'passport' ? 'active' : ''}`}
                  onClick={() => setActiveRightTab('passport')}
                >
                  Thermal Passport
                </button>
                <button 
                  className={`p-tab ${activeRightTab === 'chat' ? 'active' : ''}`}
                  onClick={() => setActiveRightTab('chat')}
                >
                  AI Assistant
                </button>
              </div>

              {activeRightTab === 'passport' && (
                <div className="panel-body">
                  <div className="building-passport">
                    <div className="passport-header">
                      <span className="passport-badge">BUILDING METRICS PASSPORT</span>
                      <h3>{selectedBuilding?.name || 'Central District Facility'}</h3>
                      <p>{selectedBuilding?.id || 'BLD_ASTANA_CENTRAL'}</p>
                    </div>

                    <div className="passport-stats-grid">
                      <div className="p-stat">
                        <span className="p-label">Floors</span>
                        <span className="p-val">{selectedBuilding?.floors || 16}</span>
                      </div>
                      <div className="p-stat">
                        <span className="p-label">Height</span>
                        <span className="p-val">{selectedBuilding?.height || 52}m</span>
                      </div>
                      <div className="p-stat">
                        <span className="p-label">Heat Loss</span>
                        <span className="p-val text-warning">84.5 kW</span>
                      </div>
                      <div className="p-stat">
                        <span className="p-label">SNiP R-Val</span>
                        <span className="p-val">0.85</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeRightTab === 'chat' && (
                <div className="panel-body chat-body">
                  <div className="chat-messages-scroll">
                    {chatMessages.map((m, idx) => (
                      <div key={idx} className={`chat-bubble ${m.role}`}>
                        {m.content}
                      </div>
                    ))}
                  </div>

                  <form onSubmit={handleSendMessage} className="chat-input-form">
                    <input 
                      type="text" 
                      placeholder="Enter query for Astana Twin..." 
                      value={chatInput} 
                      onChange={(e) => setChatInput(e.target.value)}
                    />
                    <button type="submit">Submit</button>
                  </form>
                </div>
              )}
            </aside>
          </div>
        )}

        {/* VIEW MODE 2: ANALYTICS DASHBOARD (Exact Image 1 Layout) */}
        {viewMode === 'dashboard' && (
          <div className="dashboard-grid-layout animate-fadeIn">
            <div className="dash-col col-gauge-left">
              <ArcGauge title="Heading" value={11000} maxValue={15000} delta="-4 000" footerText="Оставляем место для длинных заголовков, ед.изм" />
              <ArcGauge title="Heading" value={11000} maxValue={15000} delta="-4 000" footerText="Оставляем место для длинных заголовков, ед.изм" />
              <ArcGauge title="Heading" value={11000} maxValue={100} delta="-4 000" footerText="Оставляем место для длинных заголовков, ед.изм" />
            </div>

            <div className="dash-col col-main-widgets">
              <div className="group-heading-header">
                <h2>Group heading <small>Subtitle</small></h2>
              </div>

              <div className="center-top-row">
                <StackedBarWidget title="Heading" />
                <ProgressBarWidget title="Heading" />
                <SplineAreaWidget title="Heading" />
              </div>

              <div className="center-mid-row">
                <SplineAreaWidget title="Heading" />
                <ProgressBarWidget title="Heading" />
              </div>

              <div className="center-bottom-row">
                <StatGridWidget title="Group heading" subtitle="Subtitle" />
                <VarianceBarWidget title="Heading" />
              </div>
            </div>

            <div className="dash-col col-gauge-right">
              <ArcGauge title="Heading" value={11000} maxValue={15000} delta="-4 000" footerText="Оставляем место для длинных заголовков, ед.изм" />
              <ArcGauge title="Heading" value={11000} maxValue={15000} delta="-4 000" footerText="Оставляем место для длинных заголовков, ед.изм" />
              <ArcGauge title="Heading" value={11000} maxValue={100} delta="-4 000" footerText="Оставляем место для длинных заголовков, ед.изм" />
            </div>
          </div>
        )}

        {/* VIEW MODE 3: STREET TELEMETRY (Detailed 3D Street Inspector) */}
        {viewMode === 'street' && (
          <div className="street-view-layout animate-fadeIn">
            <div className="street-map-flex">
              <MapComponent 
                geoJSONData={geoJSONData}
                activeBuildingId={activeBuildingId}
                onSelectBuilding={(id) => setActiveBuildingId(id)}
                onBoundsChange={(bounds) => fetchBuildings(bounds)}
                onViewportChange={(vp) => setViewState(vp)}
                roadsGeoJSON={roadsGeoJSON}
                mapMode="dual"
                selectedStreet={selectedStreet || ASTANA_STREETS[0]}
                onSelectStreet={(st) => handleSelectStreet(st)}
                cameraPreset={cameraPreset}
                theme={themeMode}
              />
            </div>

            <StreetDetailPanel 
              selectedStreet={selectedStreet || ASTANA_STREETS[0]}
              onSelectBuilding={(id) => setActiveBuildingId(id)}
              onResetStreet={() => setViewMode('twin')}
              onCameraPreset={(preset) => setCameraPreset(preset)}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
