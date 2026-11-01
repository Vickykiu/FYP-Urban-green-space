import { useEffect, useRef, useState } from 'react';
import GreenMap from './components/GreenMap.jsx';
import LocationDialog from './components/LocationDialog.jsx';
import NearbyDetails from './components/NearbyDetails.jsx';
import Icon from './components/Icon.jsx';
import NoticeDialog from './components/NoticeDialog.jsx';
import { useMapData } from './useMapData.js';
import { DEFAULT_RADIUS, formatDistance, validRadius, withinDistrict } from './location.js';
import { searchNearby } from './nearbyApi.js';
import { MAP_ERROR } from './prototype.js';
import district from '../../data/petaling-district.json';

const EMPTY = [];
const INITIAL = { features: EMPTY, count: null, limited: false, loading: false, error: '' };
export default function NearbyPage({ initialLocation, onAnalyse }) {
  const [origin, setOrigin] = useState(null), [picker, setPicker] = useState(initialLocation ? { initial: initialLocation } : null);
  const [choice, setChoice] = useState(String(DEFAULT_RADIUS)), [custom, setCustom] = useState('1000');
  const radius = choice === 'custom' ? custom : choice;
  const [bbox, setBbox] = useState(''), [revision, setRevision] = useState(0);
  const [results, setResults] = useState(INITIAL), [notice, setNotice] = useState(null);
  const [selected, setSelected] = useState(null), [details, setDetails] = useState(null);
  const [focus, setFocus] = useState(null), [searchView, setSearchView] = useState(null);
  const request = useRef(null), generation = useRef(0), locationButton = useRef(null), resultHeading = useRef(null);
  const areas = useMapData('/api/public/administrative-areas/', { bbox }, Boolean(bbox), revision);
  useEffect(() => () => { generation.current += 1; request.current?.abort(); }, []);
  function invalidate() {
    generation.current += 1; request.current?.abort(); setResults(INITIAL); setSelected(null); setDetails(null); setNotice(null);
  }
  function openPicker(initial = origin) { setPicker({ initial }); }
  function confirm(location) { invalidate(); setOrigin(location); setPicker(null); setSearchView({ ...location, at: Date.now() }); }
  async function search(event) {
    event?.preventDefault();
    if (!origin) { openPicker(); return; }
    if (!withinDistrict(origin) || !validRadius(radius)) {
      setNotice({ title: 'Search could not be started', subtitle: 'Check the search settings.',
        message: 'Select a location in Petaling District and a whole-number radius from 100 to 10,000 m.', guidance: 'Update the search settings and try again.' }); return;
    }
    invalidate(); const current = generation.current, controller = new AbortController(); request.current = controller;
    const timeout = setTimeout(() => controller.abort('timeout'), 20000);
    setResults({ ...INITIAL, loading: true });
    try {
      const data = await searchNearby(origin, radius, { signal: controller.signal });
      if (current !== generation.current) return;
      setResults({ ...data, loading: false, error: '' });
      setSearchView({ ...origin, radius_m: Number(radius), at: Date.now() });
      if (data.count === 0) setNotice({ title: 'No nearby green spaces found', subtitle: 'No records match this search.',
        message: 'There are no uploaded green spaces within the selected radius.', guidance: 'Try a larger radius or select another starting location.' });
    } catch (problem) {
      if (current !== generation.current) return;
      const message = controller.signal.reason === 'timeout' ? 'The search took too long. Please try again.' : problem.message;
      setResults({ ...INITIAL, error: message });
      setNotice({ title: 'Nearby search could not be completed', subtitle: 'Unable to display nearby green spaces.',
        message, guidance: 'Please check the location and connection, then try again.', retry: 'search' });
    } finally { clearTimeout(timeout); }
  }
  function closeDetails() { setDetails(null); resultHeading.current?.focus({ preventScroll: true }); }
  return <main className="nearby-workspace" id="map-content" tabIndex={-1}>
    <form className="nearby-toolbar" onSubmit={search} noValidate>
      <div className="starting-location-field"><label className="field-label" htmlFor="starting-location">STARTING LOCATION</label>
        <button type="button" id="starting-location" ref={locationButton} className="location-input starting-location-button" onClick={() => openPicker()}>
          <Icon name="pin" size={17} /><span>{origin?.label || 'Select Location'}</span></button></div>
      <div className="radius-field"><label className="field-label" htmlFor="search-radius">SEARCH RADIUS</label>
        <select id="search-radius" className="location-input" value={choice} onChange={event => { invalidate(); setChoice(event.target.value); }}>
          <option value="500">500 m</option><option value="1000">1 km</option><option value="2000">2 km</option><option value="custom">Custom</option></select>
        {choice === 'custom' && <div className="custom-radius"><input aria-label="Custom radius in metres" type="number" min="100" max="10000" step="1"
          value={custom} onChange={event => { invalidate(); setCustom(event.target.value); }} /><span>m</span></div>}</div>
      <button className="primary-button nearby-submit" type="submit" disabled={results.loading} aria-busy={results.loading}><Icon name="search" size={17} />Search nearby</button>
    </form>
    <div className="nearby-content">
      <section className="map-card" aria-label="Nearby green-space map">
        <GreenMap greens={results.features} boundaries={areas.error ? district.features : areas.features} seedVisible={Boolean(areas.error)}
          onBounds={setBbox} onPick={openPicker} origin={origin} radius={results.count !== null ? Number(radius) : null}
          searchView={searchView} selectedId={selected?.id} focus={focus} onSelect={setSelected} onDetails={feature => { setSelected(feature); setDetails(feature); }} />
        <button type="button" className="map-search nearby-map-search" onClick={() => openPicker()}><Icon name="search" size={16} /><span>Search location...</span></button>
        {areas.error && <button className="map-error-button icon-button" aria-label="Show map loading error" onClick={() => setNotice({ ...MAP_ERROR, retry: 'map' })}><Icon name="info" /></button>}
      </section>
      <aside className="nearby-results" aria-label="Nearby green-space results">
        <h2 tabIndex={-1} ref={resultHeading}>{results.count === null ? 'Nearby green spaces' : `${results.count} nearby green ${results.count === 1 ? 'space' : 'spaces'}`}</h2>
        <p className="section-description">Sorted by distance from selected location</p>
        <div aria-live="polite" className="nearby-result-status">
          {results.loading ? 'Searching nearby green spaces…' : results.error ? 'Search unavailable. Please try again.'
            : results.count === null ? 'Select a starting location and search.' : results.count === 0 ? 'No nearby green spaces found.' : `${results.count} ${results.count === 1 ? 'result' : 'results'} within ${formatDistance(Number(radius))}.`}
        </div>
        <ol className="nearby-list">{results.features.map((feature, index) => <li key={feature.id} className={`nearby-result ${selected?.id === feature.id ? 'selected' : ''}`}>
          <div className="nearby-result-top"><span className={`result-number rank-${index % 3}`}>{index + 1}</span>
            <div><button className="result-name" onClick={() => { setSelected(feature); setFocus({ feature, at: Date.now() }); }}>{feature.properties.name}</button>
              <p>{feature.properties.category_name}</p></div>
            <span className="distance-badge">{formatDistance(feature.properties.distance_m)}</span></div>
          <div className="result-meta"><span><Icon name="pin" size={14} />Straight-line distance</span><span>Hours not provided</span></div>
          <div className="result-actions"><button className="text-button" onClick={() => { setSelected(feature); setDetails(feature); }}>View details</button>
            <button disabled={!origin || !validRadius(radius)} title="Analyse coverage from the confirmed starting location"
              onClick={() => onAnalyse({ location: origin, radius: Number(radius), confirmed: true })}>Analyse →</button></div>
        </li>)}</ol>
        {results.limited && <p className="inline-notice">Showing {results.features.length} of {results.count} results. Reduce the search radius to see a smaller set.</p>}
        <button className="continue-location" disabled={!origin || !validRadius(radius)}
          onClick={() => onAnalyse({ location: origin, radius: Number(radius), confirmed: true })}><Icon name="target" size={18} /><span>
          <strong>Continue with selected location</strong><small>Generate distance-based coverage</small></span></button>
      </aside>
    </div>
    {picker && <LocationDialog initial={picker.initial} onConfirm={confirm} onCancel={() => { setPicker(null); locationButton.current?.focus({ preventScroll: true }); }} />}
    {details && <NearbyDetails feature={details} onClose={closeDetails} onView={feature => { setFocus({ feature, at: Date.now() }); closeDetails(); }} />}
    <NoticeDialog notice={notice} onClose={() => setNotice(null)} onAction={notice?.retry === 'search' ? search
      : notice?.retry === 'map' ? () => { setNotice(null); setRevision(value => value + 1); } : undefined} />
  </main>;
}
