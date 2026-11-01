import { percentLabel } from '../dashboardApi.js';
import { formatCoverageArea } from '../coverageApi.js';
import { reportDate } from '../reportApi.js';

export default function ReportDocument({ snapshot: s, compact = false }) {
  const has = section => s.sections.includes(section);
  return <article className={`report-document ${compact ? 'compact-report' : ''}`}>
    <p className="report-brand">URBAN GREEN SPACE ACCESSIBILITY</p><h2>{s.area_name}</h2>
    <p className="report-period">Planning Support Report • {s.reporting_period}</p>
    <p className="report-asof">Snapshot generated {reportDate(s.generated_at)}. Reporting period is a label, not a historical filter.</p>
    {has('executive_summary') && <section><h3>Executive summary</h3><p>{percentLabel(s.summary.coverage_percentage)} of the selected planning area's land is within 1 km of uploaded green spaces. {s.summary.space_count} green-space records intersect this area.</p></section>}
    {has('coverage_indicators') && <section><div className="report-indicators"><div><span>Coverage</span><strong>{percentLabel(s.summary.coverage_percentage)}</strong><small>Land area · 1 km</small></div>
      <div><span>Population gap</span><strong>Unavailable</strong></div><div><span>Priority</span><strong>Not assessed</strong></div></div>
      <p className="subtle">Mapped green-space area: {formatCoverageArea(s.summary.green_area_ha)}{s.summary.area_status === 'partial' ? ' (mapped polygons only; partial)' : ''}.</p></section>}
    {has('priority_gap') && <section><h3>Recommended planning action</h3><p className="report-note">No intervention recommendation has been generated. Population data and agreed priority criteria are required.</p></section>}
    {has('coverage_indicators') && <section><h3>Coverage by sub-zone</h3><p className="subtle">Available administrative areas; no unverified sub-zones are invented. Overlapping areas are not additive.</p>
      <div className="report-area-bars">{s.areas.map(row => <div key={row.area_id}><span>{row.area_name}</span><div className="report-bar-track"><span style={{ width: `${row.coverage_percentage}%` }} /></div><strong>{percentLabel(row.coverage_percentage)}</strong></div>)}</div></section>}
    {has('inventory') && <section><h3>Green-space inventory</h3><p className="subtle">{s.inventory_limited ? `Showing 1,000 of ${s.summary.space_count} records; indicators include all records.` : `${s.inventory.length} records.`} Recorded area is the supplied value, not the clipped footprint measurement.</p>
      <div className="report-table-scroll"><table><thead><tr><th>Name</th><th>Category</th><th>Geometry</th><th>Recorded area (ha)</th></tr></thead><tbody>{s.inventory.map(row => <tr key={row.green_space_id}><td>{row.name}</td><td>{row.category_name}</td><td>{row.geometry_type}</td><td>{row.recorded_area_ha ?? 'Not provided'}</td></tr>)}</tbody></table></div></section>}
    {has('methodology') && <section><h3>Methodology notes</h3><p>Category-matching park geometries are buffered by 1,000 metres, dissolved, clipped to the study area and measured as land area. Park footprints are clipped and dissolved separately; points have no assumed footprint.</p></section>}
    <section className="report-limitations"><h3>Data limitations</h3><ul>{s.limitations.map(note => <li key={note}>{note}</li>)}</ul></section>
  </article>;
}
