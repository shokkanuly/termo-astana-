import React from 'react';

export default function ProgressBarWidget({ 
  title = "Heading",
  rows = [
    { current: 8000, max: 15000, delta: "7 000", segments: [40, 30, 30], pinPct: 55 },
    { current: 12000, max: 34000, delta: "24 000", segments: [35, 45, 20], pinPct: 40 },
    { current: 13000, max: 15000, delta: "2 000", segments: [50, 25, 25], pinPct: 80 }
  ]
}) {
  return (
    <div className="widget-card progress-bars-card">
      <div className="widget-header">
        <span className="widget-title">{title}</span>
        <span className="widget-menu-icon">•••</span>
      </div>

      <div className="progress-bars-list">
        {rows.map((row, idx) => (
          <div className="progress-bar-item" key={idx}>
            <div className="progress-item-header">
              <span className="val-bold">{row.current.toLocaleString()}</span>
              <span className="val-max">{row.max.toLocaleString()}</span>
              <span className="val-delta">Δ{row.delta}</span>
            </div>

            <div className="progress-track-wrapper">
              <div className="progress-track-segments">
                <div className="seg seg-primary" style={{ width: `${row.segments[0]}%` }} />
                <div className="seg seg-warning" style={{ width: `${row.segments[1]}%` }} />
                <div className="seg seg-neutral" style={{ width: `${row.segments[2]}%` }} />
              </div>
              
              <div className="progress-indicator-pin" style={{ left: `${row.pinPct}%` }}>
                <div className="pin-head" />
                <div className="pin-line" />
              </div>
            </div>

            <div className="progress-item-footer">
              <span>0</span>
              <span>{Math.round(row.max / 2).toLocaleString()}</span>
              <span>{row.max.toLocaleString()}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
