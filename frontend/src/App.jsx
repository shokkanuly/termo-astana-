import React, { useState, useEffect, useRef } from 'react';
import { 
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend 
} from 'recharts';
import { 
  Search, ShieldAlert, Cpu, Activity, Info, TrendingUp, Zap, HelpCircle, Thermometer, Wind, Droplets, MapPin
} from 'lucide-react';
import MapComponent from './MapComponent';
import './App.css';

function App() {
  const [activeBuildingId, setActiveBuildingId] = useState(null);
  const [geoJSONData, setGeoJSONData] = useState(null);
  const [stats, setStats] = useState({
    total_nodes: 0,
    hardware_nodes: 0,
    virtual_nodes: 0,
    outside_temp: -15.0,
    humidity: 60.0,
    wind_speed: 3.5,
    peak_heat_loss_w: 0.0
  });
  
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBuildingData, setSelectedBuildingData] = useState(null);
  const [selectedBuilding, setSelectedBuilding] = useState(null);
  const [tickerRows, setTickerRows] = useState([]);
  
  // Map HUD coordinates state
  const [viewState, setViewState] = useState({
    longitude: 71.4305,
    latitude: 51.1283,
    zoom: 14.5,
    pitch: 45,
    bearing: -15
  });

  // Radius search state
  const [radiusActive, setRadiusActive] = useState(false);
  const [radiusMeters, setRadiusMeters] = useState(1000);
  const [radiusSearchResults, setRadiusSearchResults] = useState([]);
  const [radiusCenter, setRadiusCenter] = useState(null);

  const ws = useRef(null);

  // 1. Fetch GeoJSON buildings when viewport bounds change
  const fetchBuildings = async (bounds) => {
    if (!bounds || viewState.zoom < 14) {
      setGeoJSONData({ type: 'FeatureCollection', features: [] });
      return;
    }
    const { west, south, east, north } = bounds;
    const url = `/api/v1/buildings/geojson?min_lon=${west}&min_lat=${south}&max_lon=${east}&max_lat=${north}`;
    try {
      const res = await fetch(url);
      const data = await res.json();
      setGeoJSONData(data);
      
      // Auto-select first building if none selected
      if (!activeBuildingId && data.features?.length > 0) {
        setActiveBuildingId(data.features[0].properties.id);
      }
    } catch (e) {
      console.error("Failed to load buildings GeoJSON:", e);
    }
  };

  // 2. Fetch building physical & economic analysis
  const fetchAnalysis = async (id) => {
    if (!id) return;
    try {
      const res = await fetch(`/api/v1/building/${id}/analysis`);
      if (res.ok) {
        const data = await res.json();
        setSelectedBuildingData(data);
      }
    } catch (e) {
      console.error(`Failed to analyze building ${id}:`, e);
    }
  };

  // 3. Fetch system stats
  const fetchStats = async () => {
    try {
      const res = await fetch('/api/v1/stats');
      const data = await res.json();
      setStats(data);
    } catch (e) {
      console.error("Failed to fetch system stats:", e);
    }
  };

  // Click handler on map (handles radius query coordinates)
  const onMapClick = (evt) => {
    if (radiusActive) {
      const { lng, lat } = evt.lngLat;
      setRadiusCenter({ lng, lat });
      performRadiusSearch(lng, lat);
    }
  };

  const performRadiusSearch = async (lon, lat) => {
    try {
      const res = await fetch(`/api/v1/spatial/search?lon=${lon}&lat=${lat}&radius_meters=${radiusMeters}`);
      const data = await res.json();
      setRadiusSearchResults(data);
    } catch (e) {
      console.error("Radius search failed:", e);
    }
  };

  useEffect(() => {
    // Connect WebSocket stream for real-time telemetry
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws.current = new WebSocket(`${protocol}//${window.location.host}/ws/telemetry`);
    
    ws.current.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'telemetry') {
        const reading = msg.data;
        
        // Add to scrolling ticker (keep last 30 rows)
        setTickerRows(prev => [reading, ...prev].slice(0, 30));
        
        // Dynamic in-memory update to map polygons for real-time reactivity
        setGeoJSONData(prevData => {
          if (!prevData || !prevData.features) return prevData;
          return {
            ...prevData,
            features: prevData.features.map(f => {
              if (f.properties.id === reading.building_id) {
                return {
                  ...f,
                  properties: {
                    ...f.properties,
                    heat_loss_w: reading.heat_loss_w,
                    severity: reading.severity
                  }
                };
              }
              return f;
            })
          };
        });

        // If the reading matches our active building or prototype, refresh calculations
        if (reading.building_id === activeBuildingId || reading.node_id === 'esp32_hw_01') {
          fetchAnalysis(activeBuildingId);
        }
      }
    };

    return () => {
      if (ws.current) ws.current.close();
    };
  }, [activeBuildingId]);

  // Periodically fetch stats on a 10s interval to prevent overloading the event loop
  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeBuildingId) {
      fetchAnalysis(activeBuildingId);
    }
  }, [activeBuildingId]);

  // Extract simple list of buildings inside current view for sidebar list
  const buildingList = geoJSONData?.features?.map(f => f.properties) || [];
  
  // Filter list based on search bar query
  const filteredBuildings = buildingList.filter(b => 
    b.address.toLowerCase().includes(searchQuery.toLowerCase()) ||
    b.material.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Check if there are any active anomalies in the live ticker streams
  const hasActiveAnomaly = tickerRows.some(row => row.is_anomaly);

  return (
    <div className="app-container">
      {/* Sci-fi Top HUD bar */}
      <header className="app-header">
        <div className="header-left">
          <span className="pulse-dot mr-2"></span>
          СБОР ДАННЫХ С ДАТЧИКОВ: {stats.total_nodes}/100 ОНЛАЙН
        </div>
        
        <div className="header-center">
          <h1 className="header-title">ТЕРМОАСТАНА: ЦИФРОВОЙ ДВОЙНИК</h1>
        </div>
        
        <div className="header-right">
          АНАЛИЗ ТЕПЛОВЫХ ПОТЕРЬ: УСПЕШНО
        </div>
      </header>

      {/* DASHBOARD CONTENT */}
      <div className="app-content">
        
        {/* LEFT SIDEBAR: BUILDINGS DATABASE */}
        <aside className="left-panel">
          <div className="panel-header">
            <div className="panel-title">Реестр Зданий (Esil District)</div>
            <div className="relative">
              <input 
                type="text" 
                placeholder="Поиск по адресу или материалу..." 
                className="search-input"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
              <Search size={14} className="absolute right-3 top-2.5 text-muted" />
            </div>
          </div>
          
          <div className="buildings-list">
            {filteredBuildings.length === 0 ? (
              <div className="text-center text-muted mt-5">Нет объектов в поле зрения</div>
            ) : (
              filteredBuildings.map(b => (
                <div 
                  key={b.id} 
                  className={`building-card ${b.id === activeBuildingId ? 'active' : ''}`}
                  onClick={() => {
                    setActiveBuildingId(b.id);
                    setSelectedBuilding(b);
                  }}
                >
                  <div className="building-address">{b.address}</div>
                  <div className="building-details">
                    <span>{b.material.replace('_', ' ')}</span>
                    <span>H: {b.height}м</span>
                  </div>
                  <div className="building-loss-badge">
                    <span className="text-muted">Потери: {(b.heat_loss_w / 1000).toFixed(1)} кВт</span>
                    <span className={`severity-indicator severity-${b.severity}`}>
                      {b.severity}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </aside>

        {/* CENTER: INTERACTIVE 3D MAP */}
        <main className="map-container">
          {/* MAP HUD OVERLAY */}
          <div className="map-hud-overlay">
            <div className="map-hud-title">Координаты Визора</div>
            <div className="map-hud-row">
              <span className="map-hud-label">Lat / Lng</span>
              <span className="map-hud-value">{viewState.latitude.toFixed(4)}, {viewState.longitude.toFixed(4)}</span>
            </div>
            <div className="map-hud-row">
              <span className="map-hud-label">Зум / Наклон</span>
              <span className="map-hud-value">{viewState.zoom.toFixed(1)} / {viewState.pitch}°</span>
            </div>
            <div className="map-hud-row">
              <span className="map-hud-label">Зданий на карте</span>
              <span className="map-hud-value">{buildingList.length}</span>
            </div>
          </div>

          {/* SPATIAL RADIAL SEARCH CONTROLS */}
          <div className="map-radius-control">
            <button 
              className={`map-radius-btn ${radiusActive ? 'active' : ''}`}
              onClick={() => {
                setRadiusActive(!radiusActive);
                setRadiusCenter(null);
                setRadiusSearchResults([]);
              }}
            >
              <MapPin size={10} className="inline mr-1" />
              {radiusActive ? "Деактивировать GIS" : "Радиальный поиск GIS"}
            </button>
            {radiusActive && (
              <>
                <select 
                  value={radiusMeters} 
                  onChange={e => setRadiusMeters(Number(e.target.value))}
                  className="search-input"
                  style={{ width: '80px', padding: '3px 6px', fontSize: '10px' }}
                >
                  <option value={300}>300м</option>
                  <option value={500}>500м</option>
                  <option value={1000}>1км</option>
                  <option value={2000}>2км</option>
                </select>
                <span className="text-muted" style={{ fontSize: '9px' }}>
                  {radiusCenter ? `Найдено: ${radiusSearchResults.length}` : "Кликните по карте..."}
                </span>
              </>
            )}
          </div>

          {/* SYSTEM HUD STATUS OVERLAY (FROM SCREENSHOT) */}
          <div className="system-status-overlay">
            <span className="system-status-label">СТАТУС СИСТЕМЫ:</span>
            {hasActiveAnomaly ? (
              <span className="system-status-value anom">АНОМАЛИЯ</span>
            ) : (
              <span className="system-status-value norm">НОРМА</span>
            )}
          </div>

          {/* ZOOM WARNING OVERLAY */}
          {viewState.zoom < 14 && (
            <div className="zoom-warning-hud">
              ⚠️ Zoom in to load thermal polygons
            </div>
          )}

          <MapComponent
            geoJSONData={geoJSONData}
            activeBuildingId={activeBuildingId}
            onSelectBuilding={(id) => {
              setActiveBuildingId(id);
              const b = buildingList.find(item => item.id === id);
              if (b) setSelectedBuilding(b);
            }}
            onBoundsChange={fetchBuildings}
            onViewportChange={setViewState}
            radiusActive={radiusActive}
            radiusMeters={radiusMeters}
            radiusCenter={radiusCenter}
            onMapClick={onMapClick}
          />
        </main>

        {/* RIGHT SIDEBAR: PASS REPORT & ROI */}
        <aside className="right-panel">
          <div className="panel-header">
            <div className="panel-title">Паспорт Теплопотерь Здания</div>
            {selectedBuilding ? (
              <div style={{ fontSize: '14px', fontWeight: 'bold' }}>
                {selectedBuilding.address}
              </div>
            ) : null}
          </div>

          {!selectedBuilding ? (
            <div className="passport-empty-state">
              <div className="empty-state-scanner"></div>
              <div className="empty-state-title">AWAITING TARGET ACQUISITION</div>
              <div className="empty-state-subtitle">SELECT A NODE ON THE MAP</div>
            </div>
          ) : (
            <div className="passport-body">
              {/* IF ACTIVE PHYSICAL ANOMALY FLAGGED */}
              {tickerRows[0]?.is_anomaly && tickerRows[0]?.building_id === activeBuildingId && (
                <div className="anomaly-alert-box">
                  <ShieldAlert size={16} className="inline mr-2 float-left" />
                  <strong>{tickerRows[0].anomaly_reason}</strong>
                </div>
              )}

              {/* PHYS SPEC CARD */}
              <div className="section-card">
                <div className="section-card-title">Физические Параметры</div>
                <div className="grid-stats">
                  <div className="grid-stat-box">
                    <span className="grid-stat-label">Материал</span>
                    <span className="grid-stat-val text-neon-cyan" style={{ fontSize: '10px' }}>
                      {selectedBuilding.material ? selectedBuilding.material.replace('_', ' ') : 'N/A'}
                    </span>
                  </div>
                  <div className="grid-stat-box">
                    <span className="grid-stat-label">Площадь фасада</span>
                    <span className="grid-stat-val">{selectedBuilding.facade_area_m2} м²</span>
                  </div>
                  <div className="grid-stat-box">
                    <span className="grid-stat-label">Высота</span>
                    <span className="grid-stat-val">{selectedBuilding.height} м</span>
                  </div>
                  <div className="grid-stat-box">
                    <span className="grid-stat-label">Окна / Кровля</span>
                    <span className="grid-stat-val">{selectedBuilding.window_area_m2} / {selectedBuilding.roof_area_m2} м²</span>
                  </div>
                </div>
              </div>

              {/* TIMESCALEDB TEMPERATURE LOGS */}
              <div className="section-card">
                <div className="section-card-title">ПОТРЕБЛЕНИЕ ЭНЕРГИИ (24ч)</div>
                {selectedBuildingData && selectedBuildingData.building_info.id === selectedBuilding.id && selectedBuildingData.history?.length > 0 ? (
                  <div className="chart-box">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={selectedBuildingData.history}>
                        <XAxis dataKey="time" stroke="#5e849f" fontSize={8} />
                        <YAxis stroke="#5e849f" fontSize={8} />
                        <Tooltip contentStyle={{ background: '#081226', borderColor: '#00f0ff' }} />
                        <Line type="monotone" dataKey="temp_in" name="Inside" stroke="#00f0ff" strokeWidth={1.5} dot={false} />
                        <Line type="monotone" dataKey="temp_out" name="Ambient" stroke="#ff7300" strokeWidth={1.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="text-center text-muted py-5" style={{ fontSize: '11px' }}>
                    Загрузка профиля энергопотребления...
                  </div>
                )}
              </div>

              {/* ROI & ENERGO CALC */}
              <div className="section-card">
                <div className="section-card-title">ИНСУЛЯЦИЯ ROI (Теплоизоляция)</div>
                {selectedBuildingData && selectedBuildingData.building_info.id === selectedBuilding.id ? (
                  <>
                    <div className="roi-pitch-text mb-3">
                      {selectedBuildingData.metrics.pitch}
                    </div>
                    <div className="grid-stats mb-3">
                      <div className="grid-stat-box">
                        <span className="grid-stat-label">Стоимость апгрейда</span>
                        <span className="grid-stat-val text-neon-orange">
                          {selectedBuildingData.metrics.estimated_cost_kzt.toLocaleString()} ₸
                        </span>
                      </div>
                      <div className="grid-stat-box">
                        <span className="grid-stat-label">Экономия в сезон</span>
                        <span className="grid-stat-val text-neon-green">
                          {selectedBuildingData.metrics.yearly_saving_kzt.toLocaleString()} ₸
                        </span>
                      </div>
                    </div>
                    
                    {/* ROI Amortization curve chart */}
                    <div className="chart-box">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={
                          selectedBuildingData.chart_data.years.map((y, idx) => ({
                            year: y,
                            'Без ремонта': selectedBuildingData.chart_data.without_renovation_accumulated_kzt[idx],
                            'С ремонтом': selectedBuildingData.chart_data.with_renovation_accumulated_kzt[idx]
                          }))
                        }>
                          <XAxis dataKey="year" stroke="#5e849f" fontSize={8} />
                          <YAxis stroke="#5e849f" fontSize={8} />
                          <Tooltip contentStyle={{ background: '#081226', borderColor: '#bd00ff' }} />
                          <Legend fontSize={8} />
                          <Bar dataKey="Без ремонта" fill="#ff073a" radius={[3, 3, 0, 0]} />
                          <Bar dataKey="С ремонтом" fill="#39ff14" radius={[3, 3, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </>
                ) : (
                  <div className="text-center text-muted py-5" style={{ fontSize: '11px' }}>
                    Расчет окупаемости инвестиций (ROI)...
                  </div>
                )}
              </div>
            </div>
          )}

          {/* REAL-TIME TELEMETRY DATA TICKER */}
          <div className="ticker-container">
            <div className="ticker-header">
              <span>IOT ТЕЛЕМЕТРИЯ TICKER</span>
              <span className="text-neon-cyan"><Activity size={10} className="inline mr-1" /> LIVE STREAM</span>
            </div>
            <div className="ticker-rows">
              {tickerRows.length === 0 ? (
                <div className="text-center text-muted py-5" style={{ fontSize: '10px' }}>
                  Ожидание входящих WebSocket пакетов...
                </div>
              ) : (
                tickerRows.map((r, i) => {
                  const isHw = r.is_hardware;
                  const isAnom = r.is_anomaly;
                  return (
                    <div 
                      key={i} 
                      className={`ticker-row ${isAnom ? 'anomaly-highlight' : (isHw ? 'hw-highlight' : '')}`}
                    >
                      <span>{r.node_id}</span>
                      <span>{r.address.split(',')[0]}</span>
                      <span>T_fac: {r.temp_facade_c}°C</span>
                      <span>Loss: {(r.heat_loss_w / 1000).toFixed(1)}кВт</span>
                      <span>{isAnom ? "🚨 ANOM!" : "OK"}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </aside>

      </div>
    </div>
  );
}

export default App;
