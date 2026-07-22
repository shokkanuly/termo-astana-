import React, { useState } from 'react';
import { 
  Navigation, Thermometer, Activity, Eye, Building2, ChevronRight, BarChart2, Layers, Cpu
} from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts';
import ElevationSlice from './ElevationSlice';

export default function StreetDetailPanel({
  selectedStreet,
  onSelectBuilding,
  onResetStreet,
  onCameraPreset
}) {
  const [activeStreetTab, setActiveStreetTab] = useState('overview'); // 'overview' | 'buildings' | 'traffic'

  if (!selectedStreet) return null;

  const streetBuildings = [
    { id: `${selectedStreet.id}_b1`, name: `${selectedStreet.nameRu}, 12`, height: 48, floors: 15, heatLoss: '48.2 kW', rVal: 0.85, status: 'MODERATE', windows: '24%' },
    { id: `${selectedStreet.id}_b2`, name: `${selectedStreet.nameRu}, 14/1`, height: 72, floors: 22, heatLoss: '112.5 kW', rVal: 0.45, status: 'HIGH LOSS', windows: '38%' },
    { id: `${selectedStreet.id}_b3`, name: `${selectedStreet.nameRu}, 18`, height: 35, floors: 10, heatLoss: '28.1 kW', rVal: 1.25, status: 'EFFICIENT', windows: '18%' },
    { id: `${selectedStreet.id}_b4`, name: `${selectedStreet.nameRu}, 22`, height: 88, floors: 28, heatLoss: '145.0 kW', rVal: 0.38, status: 'HIGH LOSS', windows: '42%' },
    { id: `${selectedStreet.id}_b5`, name: `${selectedStreet.nameRu}, 26`, height: 52, floors: 16, heatLoss: '56.4 kW', rVal: 0.92, status: 'MODERATE', windows: '22%' },
  ];

  const thermalHourlyData = [
    { time: '00:00', load: 45 },
    { time: '04:00', load: 62 },
    { time: '08:00', load: 95 },
    { time: '12:00', load: 78 },
    { time: '16:00', load: 88 },
    { time: '20:00', load: 104 },
    { time: '23:59', load: 58 },
  ];

  return (
    <div className="street-detail-panel animate-fadeIn">
      {/* Top Banner */}
      <div className="street-panel-header">
        <div className="street-title-group">
          <div className="street-badge">STREET 3D TWIN</div>
          <h2 className="street-name-display">{selectedStreet.nameRu || selectedStreet.name}</h2>
          <span className="street-sub-coords">{selectedStreet.id} • Central Sector</span>
        </div>
        
        <button className="btn-close-street" onClick={onResetStreet}>
          Close View
        </button>
      </div>

      {/* Quick Camera Angle Bar */}
      <div className="street-camera-bar">
        <span className="cam-label"><Eye size={13} /> View Angle:</span>
        <button className="btn-cam-pill" onClick={() => onCameraPreset('street_flyover')}>
          Street Flyover (65°)
        </button>
        <button className="btn-cam-pill" onClick={() => onCameraPreset('ground_3d')}>
          Ground 3D (75°)
        </button>
        <button className="btn-cam-pill" onClick={() => onCameraPreset('aerial_top')}>
          Top View (0°)
        </button>
      </div>

      {/* Street Metric Cards */}
      <div className="street-kpi-grid">
        <div className="street-kpi-card">
          <div className="kpi-icon icon-speed"><Navigation size={16} /></div>
          <div className="kpi-info">
            <span className="kpi-label">Avg Speed</span>
            <span className="kpi-value">{selectedStreet.currentSpeed || 55} <small>km/h</small></span>
          </div>
        </div>

        <div className="street-kpi-card">
          <div className="kpi-icon icon-heat"><Thermometer size={16} /></div>
          <div className="kpi-info">
            <span className="kpi-label">Street Heat Loss</span>
            <span className="kpi-value">{selectedStreet.heatLossKw || 390} <small>kW</small></span>
          </div>
        </div>

        <div className="street-kpi-card">
          <div className="kpi-icon icon-flow"><Activity size={16} /></div>
          <div className="kpi-info">
            <span className="kpi-label">Flow Index</span>
            <span className="kpi-value">{selectedStreet.flowRate || 84.5}%</span>
          </div>
        </div>
      </div>

      {/* Sub Tabs */}
      <div className="street-tabs">
        <button 
          className={`tab-btn ${activeStreetTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveStreetTab('overview')}
        >
          <Layers size={13} /> 3D Elevation Slice
        </button>
        <button 
          className={`tab-btn ${activeStreetTab === 'buildings' ? 'active' : ''}`}
          onClick={() => setActiveStreetTab('buildings')}
        >
          <Building2 size={13} /> Buildings ({streetBuildings.length})
        </button>
        <button 
          className={`tab-btn ${activeStreetTab === 'traffic' ? 'active' : ''}`}
          onClick={() => setActiveStreetTab('traffic')}
        >
          <Cpu size={13} /> Sensor Telemetry
        </button>
      </div>

      {/* Tab Content */}
      <div className="street-tab-content">
        {activeStreetTab === 'overview' && (
          <div className="street-overview-tab">
            <ElevationSlice buildings={streetBuildings} onSelectBuilding={onSelectBuilding} />

            <div className="street-chart-card">
              <div className="chart-header">
                <BarChart2 size={14} />
                <span>24-Hour Thermal Consumption (kW)</span>
              </div>
              <div style={{ width: '100%', height: 140 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={thermalHourlyData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                    <XAxis dataKey="time" stroke="#64748b" fontSize={10} />
                    <YAxis stroke="#64748b" fontSize={10} />
                    <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #00d2ff' }} />
                    <Line type="monotone" dataKey="load" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {activeStreetTab === 'buildings' && (
          <div className="street-buildings-tab">
            <div className="buildings-list-scroll">
              {streetBuildings.map((bld, idx) => (
                <div 
                  key={idx} 
                  className="street-bld-item"
                  onClick={() => onSelectBuilding && onSelectBuilding(bld.id)}
                >
                  <div className="bld-item-left">
                    <div className="bld-name">{bld.name}</div>
                    <div className="bld-meta">
                      {bld.floors} Floors • Height: {bld.height}m • Windows: {bld.windows}
                    </div>
                  </div>

                  <div className="bld-item-right">
                    <div className="bld-heat-badge">{bld.heatLoss}</div>
                    <span className={`status-pill ${bld.status.toLowerCase().replace(/\s+/g, '-')}`}>
                      {bld.status}
                    </span>
                  </div>
                  <ChevronRight size={14} className="bld-arrow" />
                </div>
              ))}
            </div>
          </div>
        )}

        {activeStreetTab === 'traffic' && (
          <div className="street-traffic-tab">
            <div className="traffic-ai-card">
              <div className="ai-status-head">
                <Cpu size={16} className="text-cyan" />
                <span>Signal Optimization Grid</span>
                <span className="badge-auto">AUTO ONLINE</span>
              </div>

              <div className="ai-meters-grid">
                <div className="ai-meter">
                  <span className="meter-label">Signal Wave Phase</span>
                  <span className="meter-val text-green">GREEN_PHASE_A</span>
                </div>
                <div className="ai-meter">
                  <span className="meter-label">CO2 Concentration</span>
                  <span className="meter-val text-amber">{selectedStreet.co2Ppm || 410} ppm</span>
                </div>
                <div className="ai-meter">
                  <span className="meter-label">Congestion Index</span>
                  <span className="meter-val text-cyan">{selectedStreet.congestionIndex || 30}%</span>
                </div>
                <div className="ai-meter">
                  <span className="meter-label">Telemetry Status</span>
                  <span className="meter-val text-green">100% NOMINAL</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
