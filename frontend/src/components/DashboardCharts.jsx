import { useEffect, useRef } from 'react';
import { Chart, BarController, BarElement, CategoryScale, LinearScale, DoughnutController, ArcElement, Tooltip } from 'chart.js';
import { DASHBOARD_COLORS, percentLabel } from '../dashboardApi.js';

Chart.register(BarController, BarElement, CategoryScale, LinearScale, DoughnutController, ArcElement, Tooltip);

export function AreaCoverageChart({ rows }) {
  const canvas = useRef(null);
  useEffect(() => {
    const chart = new Chart(canvas.current, { type: 'bar',
      plugins: [{ id: 'coverage-values', afterDatasetsDraw(chart) {
        const context = chart.ctx; context.save(); context.fillStyle = '#243b53'; context.font = '600 10px "Segoe UI", sans-serif'; context.textBaseline = 'middle';
        chart.getDatasetMeta(0).data.forEach((bar, index) => context.fillText(percentLabel(rows[index].coverage_percentage), chart.chartArea.right + 10, bar.y));
        context.restore();
      } }],
      data: { labels: rows.map(row => row.area_name), datasets: [{ label: 'Land within 1 km (%)', data: rows.map(row => row.coverage_percentage),
        backgroundColor: '#10b981', borderRadius: 6, borderSkipped: false, maxBarThickness: 13, grouped: false, order: 1 },
      { label: 'Reference: all land', data: rows.map(() => 100), backgroundColor: '#f1f5f9', borderRadius: 6, borderSkipped: false,
        maxBarThickness: 13, grouped: false, order: 2 }] },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: false,
        layout: { padding: { right: 45 } },
        plugins: { tooltip: { filter: item => item.datasetIndex === 0, callbacks: { label: context => `${percentLabel(context.raw)} of land` } } },
        scales: { x: { min: 0, max: 100, display: false },
          y: { grid: { display: false }, border: { display: false }, ticks: { color: '#52677e', font: { size: 11 }, autoSkip: false } } } } });
    return () => chart.destroy();
  }, [rows]);
  return <><div className="area-chart-scroll"><div className="area-chart" style={{ height: Math.max(220, rows.length * 40) }}>
    <canvas ref={canvas} role="img" aria-label="Land coverage within 1 km of uploaded parks by administrative area. Values are in the table below." /></div></div>
    <details className="chart-data"><summary>View coverage values</summary><table><caption>Land within 1 km of uploaded parks</caption>
      <thead><tr><th scope="col">Area</th><th scope="col">Number of spaces</th><th scope="col">Coverage</th></tr></thead>
      <tbody>{rows.map(row => <tr key={row.area_id}><th scope="row">{row.area_name} <small>{row.area_type}</small></th><td>{row.space_count}</td><td>{percentLabel(row.coverage_percentage)}</td></tr>)}</tbody></table></details></>;
}

export function CategoryChart({ rows, total }) {
  const canvas = useRef(null);
  useEffect(() => {
    if (!total) return undefined;
    const chart = new Chart(canvas.current, { type: 'doughnut',
      data: { labels: rows.map(row => row.category_name), datasets: [{ data: rows.map(row => row.space_count),
        backgroundColor: rows.map((_, index) => DASHBOARD_COLORS[index % DASHBOARD_COLORS.length]), borderWidth: 0, borderRadius: 5 }] },
      options: { responsive: true, maintainAspectRatio: false, animation: false, cutout: '73%' } });
    return () => chart.destroy();
  }, [rows, total]);
  return <div className="category-chart-content"><div className={`category-chart ${total ? '' : 'empty-doughnut'}`}>
    {total > 0 && <canvas ref={canvas} role="img" aria-label="Number of spaces by green-space category. Values are listed alongside." />}
    <div className="chart-centre"><strong>{total.toLocaleString('en-MY')}</strong><span>spaces</span></div></div>
    <ul className="dashboard-category-legend" aria-label="Category counts">{rows.map((row, index) => <li key={row.category_id}>
      <span className="category-dot" style={{ background: DASHBOARD_COLORS[index % DASHBOARD_COLORS.length] }} /><span>{row.category_name}</span><strong>{row.space_count}</strong></li>)}</ul></div>;
}
