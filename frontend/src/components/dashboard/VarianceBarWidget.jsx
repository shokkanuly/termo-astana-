import React from 'react';

export default function VarianceBarWidget({
  title = "Heading",
  items = [
    { label: 'Янв', val: 16, type: 'pos' },
    { label: 'Фев', val: 5, type: 'pos' },
    { label: 'Мар', val: -9, type: 'neg' },
    { label: 'Апр', val: 17, type: 'pos' },
    { label: 'Май', val: 67, type: 'neutral' }
  ]
}) {
  return (
    <div className="widget-card variance-bar-card">
      <div className="widget-header">
        <span className="widget-title">{title}</span>
      </div>

      <div className="variance-chart-body">
        <div className="variance-bars">
          {items.map((item, idx) => (
            <div className="variance-col" key={idx}>
              <span className={`variance-val-tag ${item.type}`}>
                {item.val > 0 ? `+${item.val}` : item.val}
              </span>

              <div className="variance-bar-wrapper">
                <div 
                  className={`variance-bar-fill ${item.type}`} 
                  style={{ height: `${Math.min(Math.abs(item.val) * 1.8, 100)}%` }} 
                />
              </div>

              <span className="variance-month">{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
