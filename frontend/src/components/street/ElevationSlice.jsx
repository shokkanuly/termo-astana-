import React from 'react';

export default function ElevationSlice({ buildings = [], onSelectBuilding }) {
  return (
    <div className="street-3d-slice-box">
      <div className="slice-title">
        <span>3D Building Elevation & Thermal Resistance Slice</span>
        <span className="live-status-dot" />
      </div>

      <div className="building-slice-visual">
        {buildings.map((bld, idx) => {
          const heightPx = Math.min(bld.height * 2.2, 120);
          const isHighLoss = bld.status === 'HIGH LOSS';
          const isModerate = bld.status === 'MODERATE';

          return (
            <div 
              key={idx} 
              className={`slice-building-bar ${isHighLoss ? 'high-loss' : isModerate ? 'moderate' : 'efficient'}`}
              style={{ height: `${heightPx}px` }}
              onClick={() => onSelectBuilding && onSelectBuilding(bld.id)}
              title={`Inspect ${bld.name}`}
            >
              <div className="slice-bld-cap">{bld.floors}F</div>
              <div className="slice-bld-window-grid" />
              <div className="slice-bld-label">{bld.name.split(',')[1] || bld.name}</div>
            </div>
          );
        })}
      </div>

      <div className="slice-road-base">
        <span>Roadway Alignment Vector</span>
      </div>
    </div>
  );
}
