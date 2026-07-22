import React from 'react';
import { 
  Map, LayoutGrid, Navigation, Eye, Layers, Sun, Moon, MapPin, Activity, Sliders
} from 'lucide-react';
import { ASTANA_STREETS } from '../../constants/astanaData';

export default function Header({
  viewMode,
  setViewMode,
  themeMode,
  setThemeMode,
  selectedStreet,
  onSelectStreet,
  cameraPreset,
  setCameraPreset
}) {
  return (
    <header className="app-header">
      {/* Brand & Main View Mode Switcher */}
      <div className="header-left">
        <div className="brand-badge">
          <div className="status-indicator-dot" />
          <span className="brand-title">ASTANA TWIN</span>
          <span className="brand-tag">3D DIGITAL TWIN SYSTEM</span>
        </div>

        <nav className="view-mode-tabs" aria-label="Main navigation">
          <button 
            className={`view-tab ${viewMode === 'twin' ? 'active' : ''}`}
            onClick={() => setViewMode('twin')}
          >
            <Map size={14} />
            <span>3D Map View</span>
          </button>

          <button 
            className={`view-tab ${viewMode === 'dashboard' ? 'active' : ''}`}
            onClick={() => setViewMode('dashboard')}
          >
            <LayoutGrid size={14} />
            <span>Analytics Dashboard</span>
          </button>

          <button 
            className={`view-tab ${viewMode === 'street' ? 'active' : ''}`}
            onClick={() => setViewMode('street')}
          >
            <Navigation size={14} />
            <span>Street Telemetry</span>
          </button>
        </nav>
      </div>

      {/* Center Street Chooser */}
      <div className="header-center">
        <div className="street-selector-box">
          <MapPin size={14} className="icon-accent" />
          <select 
            className="street-select"
            value={selectedStreet?.id || ''} 
            onChange={(e) => {
              const found = ASTANA_STREETS.find(s => s.id === e.target.value);
              onSelectStreet(found || null);
            }}
          >
            <option value="">Select Astana Street Segment...</option>
            {ASTANA_STREETS.map(st => (
              <option key={st.id} value={st.id}>
                {st.nameRu} ({st.name})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Header Right Camera & Theme Controls */}
      <div className="header-right">
        <div className="camera-preset-group">
          <button 
            className={`btn-cam-control ${cameraPreset === 'aerial_3d' ? 'active' : ''}`}
            onClick={() => setCameraPreset('aerial_3d')}
            title="3D Aerial Angle"
          >
            <Eye size={13} />
            <span>3D Aerial</span>
          </button>

          <button 
            className={`btn-cam-control ${cameraPreset === 'street_flyover' ? 'active' : ''}`}
            onClick={() => setCameraPreset('street_flyover')}
            title="Street Focus Angle"
          >
            <Navigation size={13} />
            <span>Street Tilt</span>
          </button>

          <button 
            className={`btn-cam-control ${cameraPreset === 'aerial_top' ? 'active' : ''}`}
            onClick={() => setCameraPreset('aerial_top')}
            title="2D Orthographic"
          >
            <Layers size={13} />
            <span>2D Map</span>
          </button>
        </div>

        <button 
          className="theme-switch-btn"
          onClick={() => setThemeMode(prev => prev === 'dark' ? 'light' : 'dark')}
          title={`Switch to ${themeMode === 'dark' ? 'Light' : 'Dark'} theme`}
          aria-label="Toggle Theme"
        >
          {themeMode === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>
    </header>
  );
}
