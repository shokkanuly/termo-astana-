import React from 'react';

export default function StatGridWidget({
  title = "Group heading",
  subtitle = "Subtitle",
  stats = [
    { label: "Label", value: "100" },
    { label: "Label", value: "100" },
    { label: "Label", value: "100" },
    { label: "Label", value: "100" }
  ]
}) {
  return (
    <div className="widget-card stat-grid-card">
      <div className="widget-header-with-sub">
        <span className="widget-title-lg">{title}</span>
        <span className="widget-subtitle">{subtitle}</span>
      </div>

      <div className="stat-cards-4grid">
        {stats.map((st, i) => (
          <div className="stat-mini-box" key={i}>
            <span className="stat-mini-label">{st.label}</span>
            <span className="stat-mini-value">{st.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
