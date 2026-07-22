import React from 'react';

export default function ArcGauge({ 
  title = "Heading", 
  value = 11000, 
  maxValue = 15000, 
  targetValue = 15000, 
  subValue = 15000, 
  delta = "-4 000", 
  footerText = "Оставляем место для длинных заголовков, ед.изм"
}) {
  const percentage = Math.min(Math.max((value / maxValue), 0), 1);
  const radius = 75;
  const strokeWidth = 14;
  const strokeDasharray = Math.PI * radius; // ~235.6
  const strokeDashoffset = strokeDasharray * (1 - percentage);

  return (
    <div className="widget-card arc-gauge-card">
      <div className="widget-header">
        <span className="widget-title">{title}</span>
        <span className="widget-target-badge">{targetValue ? targetValue.toLocaleString() : ''}</span>
      </div>

      <div className="arc-gauge-container">
        <svg viewBox="0 0 180 110" className="arc-gauge-svg">
          <defs>
            <linearGradient id={`gaugeGrad-${title.replace(/[^a-zA-Z0-9]/g, '')}`} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#ffffff" />
              <stop offset="60%" stopColor="#ffaa00" />
              <stop offset="100%" stopColor="#ff2a4b" />
            </linearGradient>
          </defs>

          {/* Background track */}
          <path
            d="M 15 90 A 75 75 0 0 1 165 90"
            fill="none"
            className="gauge-track-path"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />

          {/* Value filled path */}
          <path
            d="M 15 90 A 75 75 0 0 1 165 90"
            fill="none"
            stroke={`url(#gaugeGrad-${title.replace(/[^a-zA-Z0-9]/g, '')})`}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={strokeDasharray}
            strokeDashoffset={strokeDashoffset}
            style={{ transition: 'stroke-dashoffset 0.8s ease-in-out' }}
          />

          {/* Target marker notch */}
          <circle cx="130" cy="35" r="4" className="gauge-target-dot" />
        </svg>

        {/* Center Text Block - Bold & High Contrast */}
        <div className="arc-gauge-content">
          <div className="arc-main-value">{value.toLocaleString()}</div>
          <div className="arc-sub-value">{subValue.toLocaleString()}</div>
          <div className={`arc-delta-tag ${delta.startsWith('+') ? 'positive' : 'negative'}`}>
            Δ{delta}
          </div>
        </div>

        {/* Baseline Scale bounds */}
        <div className="arc-scale-labels">
          <span className="scale-min">0</span>
          <span className="scale-max">{maxValue.toLocaleString()}</span>
        </div>
      </div>

      <div className="widget-footer-text">
        {footerText}
      </div>
    </div>
  );
}
