import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';

export default function StackedBarWidget({
  title = "Heading",
  data = [
    { name: 'Уст 1', s1: 7, s2: 2, s3: 35 },
    { name: 'Уст 2', s1: 7, s2: 7, s3: 20 },
    { name: 'Уст 3', s1: 18, s2: 12, s3: 18 },
    { name: 'Уст 4', s1: 4, s2: 2, s3: 10 },
    { name: 'Уст 5', s1: 6, s2: 15, s3: 4 }
  ]
}) {
  return (
    <div className="widget-card stacked-bar-card">
      <div className="widget-header">
        <span className="widget-title">{title}</span>
        <span className="widget-menu-icon">•••</span>
      </div>

      <div className="stacked-bar-container" style={{ width: '100%', height: 160 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart layout="vertical" data={data} margin={{ top: 5, right: 10, left: -10, bottom: 5 }} barSize={12}>
            <XAxis type="number" stroke="#71717a" fontSize={10} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="name" stroke="#a1a1aa" fontSize={10} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ background: '#09090b', border: '1px solid #3f3f46', borderRadius: 2 }} />
            <Bar dataKey="s1" stackId="a" fill="#3f3f46" radius={[0, 0, 0, 0]} />
            <Bar dataKey="s2" stackId="a" fill="#a1a1aa" radius={[0, 0, 0, 0]} />
            <Bar dataKey="s3" stackId="a" fill="#ffffff" radius={[0, 2, 2, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
