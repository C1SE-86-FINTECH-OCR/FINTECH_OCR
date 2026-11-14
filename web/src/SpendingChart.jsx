import React from 'react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import {
  currentDashboardMonth,
  formatCompactVnd,
  formatDashboardMonth,
  formatDashboardMonthTick,
  formatVnd,
  recentMonthlySeries,
} from './dashboardUtils';

function SpendingTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return <div className="spending-tooltip">
    <strong>{formatDashboardMonth(label)}</strong>
    {point.invoice_count > 0
      ? <><b>{formatVnd(point.amount)}</b><small>{point.invoice_count} {point.invoice_count === 1 ? 'invoice' : 'invoices'}</small></>
      : <small>No invoices recorded · 0 VND</small>}
  </div>;
}

export default function SpendingChart({ summary }) {
  const monthly = recentMonthlySeries(summary?.monthly, currentDashboardMonth(), 12);
  const hasRecentSpending = monthly.some(row => row.hasData);
  const total = formatVnd(summary?.total_amount);

  return <section className="panel">
    <div className="panel-heading">
      <div>
        <h3>My spending by month</h3>
        <strong className="big-number">{total}</strong>
        <small className="spending-total-label">Total across visible invoices · all dates</small>
      </div>
      <div className="spending-period">
        <small>Last 12 months · VND</small>
        <small>{formatDashboardMonth(monthly[0]?.month)} – {formatDashboardMonth(monthly.at(-1)?.month)}</small>
      </div>
    </div>
    {hasRecentSpending ? <div className="chart">
      <ResponsiveContainer>
        <AreaChart data={monthly}>
          <defs>
            <linearGradient id="monthly-spending-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#a8bfea" stopOpacity=".7"/>
              <stop offset="100%" stopColor="#a8bfea" stopOpacity=".06"/>
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#ededed" vertical={false}/>
          <XAxis dataKey="month" fontSize={10} tickFormatter={formatDashboardMonthTick} interval={0} tickMargin={8}/>
          <YAxis
            fontSize={10}
            width={58}
            tickFormatter={formatCompactVnd}
            label={{ value: 'VND', angle: -90, position: 'insideLeft', offset: 9, style: { fontSize: 9, fill: '#85878e' } }}
          />
          <Tooltip content={<SpendingTooltip/>}/>
          <Area type="monotone" dataKey="amount" stroke="#4487dc" strokeWidth={2.5} fill="url(#monthly-spending-fill)" dot={false}/>
        </AreaChart>
      </ResponsiveContainer>
    </div> : <div className="empty spending-empty"><span>No invoices recorded in the last 12 months</span></div>}
  </section>;
}
