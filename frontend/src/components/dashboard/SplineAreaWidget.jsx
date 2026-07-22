import React from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';

export default function SplineAreaWidget({
  title = "Heading",
  data = [
    { name: '12, вт', val: 2400 },
    { name: '13, ср', val: 2600 },
    { name: '14, чт', val: 2100 },
    { name: '15, пт', val: 3200 },
    { name: '16, сб', val: 3000 },
    { name: '17, вс', val: 2200 },
    { name: '18, пн', val: 1900 },
  ]
}) {
  return (
    <div className="widget-card spline-area-card">
      <div className="widget-header">
        <span className="widget-title">{title}</span>
        <span className="widget-menu-icon">•••</span>
      </div>

      <div className="spline-chart-container" style={{ width: '100%', height: 160 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#ffffff" stopOpacity={0.35} />
                <stop offset="95%" stopColor="#ffffff" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <XAxis 
              dataKey="name" 
              stroke="#71717a" 
              fontSize={10} 
              tickLine={false} 
              axisLine={{ stroke: '#27272a' }} 
            />
            <YAxis hide />
            <Tooltip 
              contentStyle={{ background: '#09090b', border: '1px solid #ffffff', borderRadius: 2 }} 
              labelStyle={{ color: '#ffffff', fontSize: 11 }}
            />
            <Area 
              type="monotone" 
              dataKey="val" 
              stroke="#ffffff" 
              strokeWidth={2.5} 
              fillOpacity={1} 
              fill="url(#areaGradient)" 
              dot={{ r: 3, fill: '#000000', stroke: '#ffffff', strokeWidth: 2 }}
              activeDot={{ r: 5, fill: '#ffffff' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
