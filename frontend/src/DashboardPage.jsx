import { useEffect, useRef, useState } from 'react';
import Icon from './components/Icon.jsx';
import NoticeDialog from './components/NoticeDialog.jsx';
import { AreaCoverageChart, CategoryChart } from './components/DashboardCharts.jsx';
import { DASHBOARD_ERROR, loadDashboard, percentLabel } from './dashboardApi.js';
import { formatCoverageArea } from './coverageApi.js';

const INITIAL_FILTERS = { area: '', category: '' };
function SummaryCard({ title, icon, tone, value, note }) {
  return <article className={`dashboard-stat ${tone}`}><div className="dashboard-stat-heading"><span className="dashboard-stat-icon"><Icon name={icon} size={19} /></span>
    <div><h2>{title}</h2><strong>{value}</strong></div></div><p>{note}</p></article>;
}

export default function DashboardPage() {
  const [draft, setDraft] = useState(INITIAL_FILTERS), [applied, setApplied] = useState(INITIAL_FILTERS);
  const [data, setData] = useState(null), [options, setOptions] = useState(null);
  const [busy, setBusy] = useState(true), [error, setError] = useState(''), [showError, setShowError] = useState(false);
  const [revision, setRevision] = useState(0);
  const activeRequest = useRef(null), generation = useRef(0);
  useEffect(() => {
    const current = ++generation.current, controller = new AbortController(); activeRequest.current = controller;
    const timer = setTimeout(() => controller.abort('timeout'), 20000);
    setBusy(true); setData(null); setError(''); setShowError(false);
    loadDashboard(applied, { signal: controller.signal }).then(result => {
      if (current !== generation.current) return;
      setData(result); setOptions(result.options);
    }).catch(problem => {
      if (current !== generation.current) return;
      setError(controller.signal.reason === 'timeout' ? 'The dashboard request took too long. Please retry.' : problem.message); setShowError(true);
    }).finally(() => { clearTimeout(timer); if (current === generation.current) setBusy(false); });
    return () => { generation.current += 1; clearTimeout(timer); controller.abort(); };
  }, [applied, revision]);
  function apply(event) {
    event.preventDefault(); generation.current += 1; activeRequest.current?.abort();
    setData(null); setError(''); setShowError(false); setApplied({ ...draft });
  }
  function retry() { generation.current += 1; activeRequest.current?.abort(); setData(null); setShowError(false); setRevision(value => value + 1); }
  const pending = draft.area !== applied.area || draft.category !== applied.category;
  const summary = data?.summary;
  return <main className="dashboard-workspace" id="map-content" tabIndex={-1}>
    <form className="dashboard-filters" onSubmit={apply}>
      <label><span className="field-label">ADMINISTRATIVE AREA</span><select aria-label="ADMINISTRATIVE AREA" value={draft.area} onChange={event => setDraft({ ...draft, area: event.target.value })}>
        <option value="">All areas</option>{options?.areas.map(area => <option key={area.area_id} value={area.area_id}>{area.area_name}{area.area_type ? ` (${area.area_type})` : ''}</option>)}</select></label>
      <label><span className="field-label">GREEN-SPACE CATEGORY</span><select aria-label="GREEN-SPACE CATEGORY" value={draft.category} onChange={event => setDraft({ ...draft, category: event.target.value })}>
        <option value="">All categories</option>{options?.categories.map(category => <option key={category.category_id} value={category.category_id}>{category.category_name}</option>)}</select></label>
      <button type="submit" className="secondary-button" aria-busy={busy}><Icon name="filter" size={17} />Apply filters</button>
    </form>
    <p className="dashboard-status" role="status">{busy ? 'Loading dashboard…' : error ? 'Dashboard information cannot be displayed.'
      : pending ? 'Filters changed. Select Apply filters to update these results.' : summary?.space_count === 0 ? 'No green-space records match these filters.' : 'Showing uploaded green-space data for the applied filters.'}
      {error && <button className="text-button" onClick={() => setShowError(true)}>Retry</button>}</p>
    <section className="dashboard-stats" aria-label="Summary indicators">
      <SummaryCard title="Green-space area" icon="map" tone="green" value={summary ? formatCoverageArea(summary.green_area_ha) : '—'}
        note={!summary ? 'Awaiting data' : summary.area_status === 'unavailable' ? 'Polygon footprints unavailable' : summary.area_status === 'partial' ? 'Mapped polygons only · partial' : 'Mapped polygon footprints'} />
      <SummaryCard title="Number of spaces" icon="grid" tone="teal" value={summary ? summary.space_count.toLocaleString('en-MY') : '—'}
        note={data ? `Across ${data.areas.length} configured ${data.areas.length === 1 ? 'area' : 'areas'}` : 'Awaiting data'} />
      <SummaryCard title="Coverage" icon="target" tone="blue" value={summary ? percentLabel(summary.coverage_percentage) : '—'} note="1 km distance threshold · land area" />
      <SummaryCard title="Planning gaps" icon="report" tone="amber" value={summary ? 'Unavailable' : '—'} note="Population and priority rules not configured" />
    </section>
    <div className="dashboard-charts"><section className="dashboard-panel" aria-labelledby="area-coverage-title"><h2 id="area-coverage-title">Coverage by administrative area</h2>
      {data ? <AreaCoverageChart rows={data.areas} /> : <div className="chart-placeholder">{busy ? 'Loading coverage…' : 'Coverage information unavailable.'}</div>}
      <p className="subtle">Percentage of land within 1 km of uploaded parks; not population coverage. Overlapping administrative areas are not additive.</p>
    </section><section className="dashboard-panel" aria-labelledby="category-chart-title"><h2 id="category-chart-title">Green-space categories</h2>
      {data ? <CategoryChart rows={data.categories} total={summary.space_count} /> : <div className="chart-placeholder">{busy ? 'Loading categories…' : 'Category information unavailable.'}</div>}
    </section></div>
    <section className="dashboard-panel priority-panel" aria-labelledby="priority-title"><div className="priority-heading"><h2 id="priority-title">Priority planning areas</h2>
      <button className="text-button" disabled title="Report viewing belongs to the next stage.">View full report →</button></div>
      <div className="priority-table-scroll"><table><thead><tr>{['AREA', 'COVERAGE', 'POPULATION GAP', 'PRIORITY', 'RECOMMENDATION'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
        <tbody><tr><td colSpan={5}>Not assessed — population data and agreed priority criteria are required. No priority ranking or intervention recommendation has been generated.</td></tr></tbody></table></div>
      <p className="subtle">Distance buffers show proximity, not walking routes, entrances or barrier-aware access. Historical baseline changes are unavailable.</p>
    </section>
    <NoticeDialog notice={showError ? DASHBOARD_ERROR : null} onClose={() => setShowError(false)} onAction={retry} />
  </main>;
}
