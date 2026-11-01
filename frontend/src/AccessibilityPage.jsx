import { useEffect, useRef, useState } from 'react';
import GreenMap from './components/GreenMap.jsx';
import Icon from './components/Icon.jsx';
import LocationDialog from './components/LocationDialog.jsx';
import NearbyDetails from './components/NearbyDetails.jsx';
import NoticeDialog from './components/NoticeDialog.jsx';
import { analyseCoverage, ANALYSIS_ERROR, formatCoverageArea } from './coverageApi.js';
import { formatDistance, validRadius, withinDistrict } from './location.js';
import district from '../../data/petaling-district.json';

const EMPTY = [];
export default function AccessibilityPage({ initial, onDashboard }) {
  const [origin, setOrigin] = useState(initial?.confirmed ? initial.location : null);
  const [picker, setPicker] = useState(initial?.location && !initial.confirmed ? { initial: initial.location } : null);
  const [radius, setRadius] = useState(String(initial?.radius || 1000));
  const [custom, setCustom] = useState(![500, 1000, 2000].includes(Number(initial?.radius || 1000)));
  const [result, setResult] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [failure, setFailure] = useState(false), [selected, setSelected] = useState(null), [details, setDetails] = useState(null);
  const [view, setView] = useState(initial?.confirmed ? initial.location : null), [focus, setFocus] = useState(null);
  const request = useRef(null), generation = useRef(0), heading = useRef(null);
  useEffect(() => () => { generation.current += 1; request.current?.abort(); }, []);
  function invalidate() {
    generation.current += 1; request.current?.abort(); setBusy(false); setResult(null); setFailure(false); setError(''); setSelected(null); setDetails(null);
  }
  function pick(location = origin) { setPicker({ initial: location }); }
  function confirm(location) { invalidate(); setOrigin(location); setPicker(null); setView({ ...location, at: Date.now() }); }
  async function run(event) {
    event?.preventDefault();
    if (!origin) { pick(); return; }
    invalidate();
    if (!validRadius(radius) || !withinDistrict(origin)) {
      setError('Select a point in Petaling District and a whole-number distance from 100 to 10,000 m.'); setFailure(true); return;
    }
    const current = generation.current, controller = new AbortController(); request.current = controller;
    const timer = setTimeout(() => controller.abort('timeout'), 20000); setBusy(true);
    try {
      const data = await analyseCoverage(origin, radius, { signal: controller.signal });
      if (current !== generation.current) return;
      setResult(data); setView({ ...origin, at: Date.now(), coverage: true });
    } catch (problem) {
      if (current !== generation.current) return;
      setError(controller.signal.reason === 'timeout' ? 'The analysis took too long. Please retry.' : problem.message); setFailure(true);
    } finally { clearTimeout(timer); if (current === generation.current) setBusy(false); }
  }
  const metrics = result?.metrics;
  const legend = [...new Set([500, 1000, 2000, ...(validRadius(radius) ? [Number(radius)] : [])])].sort((a, b) => a - b);
  function closeDetails() { setDetails(null); heading.current?.focus({ preventScroll: true }); }
  return <main className="accessibility-workspace" id="map-content" tabIndex={-1}>
    <form className="coverage-toolbar" onSubmit={run} noValidate>
      <div className="starting-location-field"><label className="field-label" htmlFor="coverage-location">SELECTED LOCATION</label>
        <button id="coverage-location" type="button" className="location-input starting-location-button" onClick={() => pick()}>
          <Icon name="pin" size={16} /><span>{origin?.label || 'Select Location'}</span></button></div>
      <fieldset className="coverage-distance"><legend className="field-label">COVERAGE DISTANCE</legend>
        <div className="distance-options">{[500, 1000, 2000].map(value => <button key={value} type="button"
          aria-pressed={!custom && Number(radius) === value} className={!custom && Number(radius) === value ? 'chosen' : ''}
          onClick={() => { invalidate(); setRadius(String(value)); setCustom(false); }}>{formatDistance(value)}</button>)}</div>
        <div className="custom-coverage"><button className="text-button" type="button" aria-expanded={custom}
          onClick={() => { invalidate(); setCustom(!custom); if (custom) setRadius('1000'); }}>Custom distance</button>
          {custom && <label><input aria-label="Coverage distance in metres" type="number" min="100" max="10000" step="1" value={radius}
            onChange={event => { invalidate(); setRadius(event.target.value); }} /><span>m</span></label>}</div></fieldset>
      <button type="submit" className="primary-button coverage-run" disabled={busy} aria-busy={busy}><Icon name="target" size={17} />Run analysis</button>
    </form>
    <div className="coverage-content">
      <section className="map-card" aria-label="Accessibility coverage map">
        <GreenMap greens={result?.green_spaces.features || EMPTY} boundaries={district.features} seedVisible
          coverage={result?.coverage.features || EMPTY} origin={origin} onPick={pick} searchView={view} focus={focus}
          onSelect={setSelected} selectedId={selected?.id} onDetails={feature => { setSelected(feature); setDetails(feature); }} />
        <button className="map-search nearby-map-search" onClick={() => pick()}><Icon name="search" size={16} /><span>Search location...</span></button>
      </section>
      <aside className="coverage-results" aria-label="Coverage results">
        <div className="coverage-results-title"><h2 tabIndex={-1} ref={heading}>Coverage results</h2>
          <span className="coverage-distance-badge">{validRadius(radius) ? formatDistance(Number(radius)) : '—'}</span></div>
        <p className="sr-only" role="status">{busy ? 'Generating coverage…' : error ? 'Analysis unavailable.' : result ? 'Coverage generated. Population data unavailable.' : 'Select a location and run analysis.'}</p>
        <div className="coverage-stat"><h3>Population covered</h3><strong>{result ? 'Unavailable' : '—'}</strong><small>{result ? 'Population data not configured' : 'Run analysis to view results'}</small></div>
        <div className="coverage-stat"><h3>Green spaces reached</h3><strong>{metrics ? metrics.green_spaces_reached.toLocaleString('en-MY') : '—'}</strong>
          <small>{metrics ? `${metrics.change_from_500_m >= 0 ? '+' : ''}${metrics.change_from_500_m} vs 500 m` : 'Awaiting analysis'}</small></div>
        <div className="coverage-stat"><h3>Total accessible area</h3><strong>{metrics ? formatCoverageArea(metrics.total_accessible_area_ha) : '—'}</strong>
          <small>{metrics?.accessible_area_percentage != null ? `${metrics.accessible_area_percentage.toLocaleString('en-MY', { maximumFractionDigits: 1 })}% of zone${metrics.area_status === 'partial' ? ' · mapped polygons only' : ''}`
            : metrics ? 'Polygon footprints unavailable' : 'Awaiting analysis'}</small></div>
        <h3 className="coverage-legend-title">Coverage legend</h3><ul className="coverage-legend">{legend.map(value => <li key={value}>
          <span className={`band-dot band-${value === 500 ? 'core' : value === Number(radius) ? 'selected' : 'context'}`} />
          {formatDistance(value)} {value === Number(radius) ? 'selected' : value === 500 ? 'core' : 'context'}</li>)}</ul>
        {busy && <p className="subtle">Generating coverage…</p>}
        {error && <p className="inline-notice">{error} <button className="text-button" onClick={() => setFailure(true)}>Retry</button></p>}
        {result?.green_spaces.limited && <p className="inline-notice">Showing {result.green_spaces.features.length} of {result.green_spaces.count} parks. Indicators include all reached records.</p>}
      </aside>
    </div>
    <section className="planning-interpretation" aria-labelledby="interpretation-title"><div>
      <h2 id="interpretation-title">Planning interpretation</h2>
      <p>{metrics ? `The selected ${formatDistance(result.radius_m)} buffer reaches ${metrics.green_spaces_reached} uploaded green-space ${metrics.green_spaces_reached === 1 ? 'record' : 'records'}. Catchment area within Petaling District: ${formatCoverageArea(metrics.coverage_area_ha)}.`
        : 'Select a location and run analysis to view distance-based coverage.'}</p>
      <p>Spatial proximity only; not walking routes or barrier-aware access.{metrics?.point_records_without_footprint > 0
        ? ` ${metrics.point_records_without_footprint} point-only ${metrics.point_records_without_footprint === 1 ? 'record has' : 'records have'} no mapped footprint for area measurement.` : ''}</p>
      <div className="priority-note"><span>PRIORITY GAP</span>Not assessed — population data unavailable.</div></div>
      <button className="secondary-button" onClick={onDashboard} title="View administrative-area summaries using the dashboard's 1 km threshold."><Icon name="chart" size={16} />Open dashboard</button>
    </section>
    {picker && <LocationDialog initial={picker.initial} onConfirm={confirm} onCancel={() => setPicker(null)} />}
    {details && <NearbyDetails feature={details} onClose={closeDetails} onView={feature => { setFocus({ feature, at: Date.now() }); closeDetails(); }} />}
    <NoticeDialog notice={failure ? ANALYSIS_ERROR : null} onAction={run} closeLabel="Back"
      onClose={() => { setFailure(false); pick(); }} />
  </main>;
}
