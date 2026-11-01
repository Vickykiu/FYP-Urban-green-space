import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import GreenMap from './components/GreenMap.jsx';
import Icon from './components/Icon.jsx';
import NoticeDialog from './components/NoticeDialog.jsx';
import { formatArea, getJSON } from './mapApi.js';
import { useMapData, useMapOptions } from './useMapData.js';
import { categoryRows, MAP_ERROR } from './prototype.js';
import districtSeed from '../../data/petaling-district.json';
import NearbyPage from './NearbyPage.jsx';
import AccessibilityPage from './AccessibilityPage.jsx';
import { withinDistrict } from './location.js';

const EMPTY = [];
const DashboardPage = lazy(() => import('./DashboardPage.jsx'));
const PAGE_LINKS = { 'Interactive map': ['map', '#map-content'], 'Search nearby': ['nearby', '#nearby'], 'Accessibility': ['accessibility', '#accessibility'], 'Planning dashboard': ['dashboard', '#dashboard'] };
const currentPage = () => window.location.hash === '#dashboard' ? 'dashboard' : window.location.hash === '#accessibility' ? 'accessibility' : window.location.hash === '#nearby' ? 'nearby' : 'map';
const PAGE_TITLES = { map: 'Interactive map', nearby: 'Nearby green-space search', accessibility: 'Accessibility coverage', dashboard: 'Planning dashboard' };
const PAGE_SUBTITLES = { map: 'Explore green spaces, planning layers, and place details', nearby: 'Find public green spaces within a selected distance',
  accessibility: 'Generate distance-based green-space accessibility for a selected location', dashboard: 'Compare coverage indicators and identify priority intervention areas' };
const NAVIGATION = [['grid', 'Overview'], ['map', 'Interactive map'], ['search', 'Search nearby'],
  ['target', 'Accessibility'], ['chart', 'Planning dashboard'], ['report', 'Reports']];
const EMPTY_NOTICE = { title: 'No green spaces found', subtitle: 'There are no matching records in this map view.',
  message: 'No green spaces match the current search or category.', guidance: 'Clear the filters or move the map and try again.' };
const DETAIL_ERROR = { title: 'Details could not be loaded', subtitle: 'Unable to display the green-space details.',
  message: 'There was a problem loading the selected green space.', guidance: 'Please check the connection and try again.' };
const LIMIT_NOTICE = { title: 'Map results are limited', subtitle: 'Not all records can be displayed in this view.',
  message: 'The map displays up to 2,000 records per layer.', guidance: 'Zoom in or select a category to see a smaller area.' };

function LayerSwitch({ label, color, checked = false, onChange, unavailable = false, unavailableReason }) {
  return <label className="layer-switch" title={unavailable ? unavailableReason || 'This analysis layer is not implemented yet.' : undefined}>
    <span className="layer-dot" style={{ background: color }} /><span>{label}</span>
    <input type="checkbox" role="switch" aria-label={label} checked={checked} disabled={unavailable}
      onChange={event => onChange?.(event.target.checked)} /><span className="switch-track" aria-hidden="true" />
  </label>;
}

export default function App() {
  const [page, setPage] = useState(currentPage);
  const [nearbyStart, setNearbyStart] = useState(null);
  const [analysisStart, setAnalysisStart] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false), [bbox, setBbox] = useState('');
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 620px)').matches);
  const menuButton = useRef(null), closeMenuButton = useRef(null), detailsHeading = useRef(null);
  const [showGreen, setShowGreen] = useState(true), [showBoundaries, setShowBoundaries] = useState(true);
  const [queryInput, setQueryInput] = useState(''), [query, setQuery] = useState(''), [category, setCategory] = useState('');
  const [revision, setRevision] = useState(0), [dismissed, setDismissed] = useState('');
  const [selected, setSelected] = useState(null), [focus, setFocus] = useState(null), [detailsOpen, setDetailsOpen] = useState(false);
  const [detail, setDetail] = useState({ data: null, loading: false, error: '' });
  const options = useMapOptions(revision, page === 'map');
  const parks = useMapData('/api/public/green-spaces/', { bbox, ...(query && { q: query }), ...(category && { category }) }, page === 'map' && Boolean(bbox) && showGreen, revision);
  const areas = useMapData('/api/public/administrative-areas/', { bbox }, page === 'map' && Boolean(bbox) && showBoundaries, revision);

  useEffect(() => {
    const change = () => { setPage(currentPage()); setMenuOpen(false); setDetailsOpen(false); };
    window.addEventListener('hashchange', change);
    return () => window.removeEventListener('hashchange', change);
  }, []);
  useEffect(() => { document.title = `${PAGE_TITLES[page]} · Petaling Green Space GIS`; }, [page]);

  useEffect(() => {
    const media = window.matchMedia('(max-width: 620px)');
    const change = () => { setIsMobile(media.matches); setMenuOpen(false); };
    media.addEventListener('change', change);
    return () => media.removeEventListener('change', change);
  }, []);
  useEffect(() => {
    if (!menuOpen) return undefined;
    closeMenuButton.current?.focus();
    const escape = event => { if (event.key === 'Escape') closeMenu(); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [menuOpen]);
  useEffect(() => { if (detailsOpen) detailsHeading.current?.focus({ preventScroll: true }); }, [detailsOpen]);
  useEffect(() => {
    if (!selected) { setDetail({ data: null, loading: false, error: '' }); return undefined; }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort('timeout'), 15000);
    setDetail({ data: null, loading: true, error: '' });
    getJSON(`/api/public/green-spaces/${selected.id}/`, { signal: controller.signal }).then(data => {
      if (data.type !== 'Feature' || data.id !== selected.id || !data.properties) throw new Error('Details could not be loaded.');
      if (!controller.signal.aborted) setDetail({ data, loading: false, error: '' });
    }).catch(error => {
      if (!controller.signal.aborted || controller.signal.reason === 'timeout') setDetail({ data: null, loading: false, error: error.message });
    }).finally(() => clearTimeout(timeout));
    return () => { clearTimeout(timeout); controller.abort(); };
  }, [selected, revision]);

  function retry() { setRevision(value => value + 1); }
  function openNearby() {
    const coordinates = selected?.geometry?.type === 'Point' ? selected.geometry.coordinates : null;
    const location = coordinates ? { latitude: coordinates[1], longitude: coordinates[0], label: selected.properties.name } : null;
    setNearbyStart(location && withinDistrict(location) ? location : null);
    setPage('nearby'); setDetailsOpen(false);
    window.location.hash = 'nearby';
  }
  function closeMenu() { setMenuOpen(false); menuButton.current?.focus(); }
  function openAccessibility(start) {
    if (!start) {
      const coordinates = selected?.geometry?.type === 'Point' ? selected.geometry.coordinates : null;
      const location = coordinates ? { latitude: coordinates[1], longitude: coordinates[0], label: selected.properties.name } : null;
      start = { location: location && withinDistrict(location) ? location : null, radius: 1000, confirmed: false };
    }
    setAnalysisStart(start); setPage('accessibility'); setMenuOpen(false); setDetailsOpen(false); window.location.hash = 'accessibility';
  }
  function clearFilters() { setCategory(''); setQuery(''); setQueryInput(''); setSelected(null); setDetailsOpen(false); }
  function chooseCategory(value) { setCategory(category === value ? '' : value); setSelected(null); setDetailsOpen(false); }
  function closeDetails() { setDetailsOpen(false); document.getElementById('selected-title')?.focus({ preventScroll: true }); }
  const properties = (detail.data?.id === selected?.id ? detail.data?.properties : null) || selected?.properties;
  const dataError = parks.error || areas.error || options.error;
  const busy = parks.loading || areas.loading || options.loading;
  const empty = !busy && !dataError && showGreen && parks.count === 0 && Boolean(query || category);
  const limited = !busy && !dataError && (parks.limited || areas.limited);
  const notice = dataError ? MAP_ERROR : detail.error && selected ? DETAIL_ERROR : empty ? EMPTY_NOTICE : limited ? LIMIT_NOTICE : null;
  // Closing a connection error survives panning; an explicit Retry can reopen it.
  const noticeKey = notice ? `${notice.title}:${revision}:${notice === EMPTY_NOTICE ? `${query}:${category}:${bbox}` : notice === DETAIL_ERROR ? selected?.id : ''}` : '';
  const showNotice = notice && dismissed !== noticeKey;
  const seedVisible = showBoundaries && Boolean(areas.error);
  const categories = categoryRows(options.data?.categories || []);

  return <>
    <div className="app-shell">
      <a className="skip-link" href="#map-content" onClick={event => {
        event.preventDefault(); document.getElementById('map-content')?.focus();
      }}>Skip to map</a>
      {menuOpen && <button className="nav-backdrop" aria-label="Close navigation backdrop" onClick={closeMenu} />}
      <aside className={`sidebar ${menuOpen ? 'open' : ''}`} inert={isMobile && !menuOpen}>
        <button ref={closeMenuButton} className="mobile-menu close-menu icon-button" aria-label="Close navigation" onClick={closeMenu}><Icon name="close" /></button>
        <a className="brand" href="#map-content" onClick={() => { setPage('map'); setMenuOpen(false); setDetailsOpen(false); }}>
          <span className="brand-symbol"><Icon name="tree" size={24} /></span>
          <span><strong>URBAN GREEN</strong><small>PLANNING GIS</small></span>
        </a>
        <p className="nav-caption">PUBLIC PORTAL</p>
        <nav aria-label="Public portal">
          {NAVIGATION.map(([icon, label]) => PAGE_LINKS[label]
            ? <a className={`nav-link ${page === PAGE_LINKS[label][0] ? 'active' : ''}`}
              aria-current={page === PAGE_LINKS[label][0] ? 'page' : undefined}
              href={PAGE_LINKS[label][1]} key={label}
              onClick={() => { setPage(PAGE_LINKS[label][0]); setMenuOpen(false); setDetailsOpen(false);
                if (label === 'Search nearby') setNearbyStart(null); if (label === 'Accessibility') setAnalysisStart(null); }}><Icon name={icon} />{label}</a>
            : <button className="nav-link" disabled title="This page is not implemented yet." key={label}><Icon name={icon} />{label}</button>)}
          <a className="nav-link admin-link" href="http://127.0.0.1:8000/admin/"><Icon name="login" />Admin login</a>
        </nav>
      </aside>
      <div className="workspace">
        <header className="page-header">
          <button ref={menuButton} className="mobile-menu icon-button" aria-label="Open navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><Icon name="menu" /></button>
          <div><h1>{PAGE_TITLES[page]}</h1><p>{PAGE_SUBTITLES[page]}</p></div>
          <span className="header-icon"><Icon name="grid" /></span>
        </header>
        {import.meta.env.MODE === 'ui-test' && <div className="test-banner">UI TEST — SYNTHETIC DATA. Not live PostGIS or real park records.</div>}
        {page === 'dashboard' ? <Suspense fallback={<main id="map-content" className="dashboard-workspace" tabIndex={-1}><p role="status">Loading dashboard…</p></main>}><DashboardPage /></Suspense>
          : page === 'accessibility' ? <AccessibilityPage initial={analysisStart} onDashboard={() => { setPage('dashboard'); window.location.hash = 'dashboard'; }} />
          : page === 'nearby' ? <NearbyPage initialLocation={nearbyStart} onAnalyse={openAccessibility} /> : <main className="map-workspace" id="map-content" tabIndex={-1}>
          <section className="map-card" aria-label="Green-space map">
            <GreenMap greens={showGreen ? parks.features : EMPTY} boundaries={showBoundaries ? (seedVisible ? districtSeed.features : areas.features) : EMPTY}
              selectedId={selected?.id} focus={focus} seedVisible={seedVisible} onBounds={setBbox} onSelect={setSelected}
              onDetails={feature => { setSelected(feature); setDetailsOpen(true); }} />
            <form className="map-search" role="search" onSubmit={event => { event.preventDefault(); setQuery(queryInput.trim()); setSelected(null); setDetailsOpen(false); }}>
              <Icon name="search" size={17} /><input aria-label="Search location" maxLength={150} type="search"
                title="Search uploaded green-space names in the current map view. Address search is not implemented yet."
                placeholder="Search location..." value={queryInput} onChange={event => { setQueryInput(event.target.value); if (!event.target.value) { setQuery(''); setSelected(null); setDetailsOpen(false); } }} />
            </form>
            <span className="sr-only" role="status">{busy ? 'Loading map records…' : dataError ? 'Map data is unavailable.' : `${parks.features.length} green spaces in this view.`}</span>
            {dataError && !showNotice && <button className="map-error-button icon-button" aria-label="Show map loading error" onClick={() => setDismissed('')}><Icon name="info" /></button>}
            {!busy && !dataError && showGreen && parks.count === 0 && !query && !category && <div className="empty-map-note" role="status">No green-space records available.</div>}
          </section>
          <aside className="controls-card" aria-label="Map controls and green-space details">
            <section className="control-section">
              <h2>Map controls</h2><p className="section-description">Configure visible planning layers</p>
              <LayerSwitch label="Urban green spaces" color="#10b981" checked={showGreen} onChange={value => { setShowGreen(value); if (!value) { setSelected(null); setDetailsOpen(false); } }} />
              <LayerSwitch label="Administrative boundaries" color="#5089f8" checked={showBoundaries} onChange={setShowBoundaries} />
              <LayerSwitch label="Accessibility coverage" color="#14b8a6" unavailable unavailableReason="Generate coverage on the Accessibility page using Run accessibility." />
              <LayerSwitch label="Priority areas" color="#f59e0b" unavailable />
            </section>
            <section className="control-section category-section">
              <h3>Green-space categories</h3>
              {categories.map(item => <button key={item.category_name} className={`category-row ${category && category === String(item.category_id) ? 'chosen' : ''}`}
                disabled={item.category_id === null} aria-pressed={category === String(item.category_id)}
                onClick={() => chooseCategory(String(item.category_id))} title="Select again to clear this category filter">
                <span className="category-swatch" />{item.category_name}<span>{item.green_space_count ?? '—'}</span></button>)}
            </section>
            <section className="control-section selected-section" aria-labelledby="selected-title">
              <h3 id="selected-title" tabIndex={-1}>Selected green space</h3>
              {!selected ? <div className="selection-placeholder"><Icon name="pin" size={26} /><p>Select a green space on the map.</p></div>
                : <><span className="category-pill">{properties.category_name}</span><h4>{properties.name}</h4>
                  <dl className="park-facts"><div><dt>Area</dt><dd>{formatArea(properties.area_size)}</dd></div>
                    <div><dt>Operating hours</dt><dd>{properties.opening_hours || 'Not provided'}</dd></div></dl></>}
              <button className="primary-button future-action" onClick={openNearby}><Icon name="search" size={16} />Search nearby</button>
              <button className="secondary-button future-action" onClick={() => openAccessibility()}><Icon name="target" size={16} />Run accessibility</button>
            </section>
          </aside>
          {detailsOpen && selected && <aside className="details-drawer" role="dialog" aria-modal="false" aria-labelledby="details-heading"
            onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); closeDetails(); } }}>
            <div className="details-heading"><h2 id="details-heading" tabIndex={-1} ref={detailsHeading}>Green-Space Details</h2>
              <button className="plain-close" aria-label="Close green-space details" onClick={closeDetails}><Icon name="close" size={16} /></button></div>
            <div className="detail-image-placeholder" aria-hidden="true"><div /></div>
            {detail.loading && <p className="subtle" role="status">Loading details…</p>}
            <dl className="detail-facts"><div><dt>Name</dt><dd>{properties.name}</dd></div>
              <div><dt>Type</dt><dd>{properties.category_name}</dd></div>
              <div><dt>Area</dt><dd>{formatArea(properties.area_size)}</dd></div>
              <div><dt>District</dt><dd>{properties.area_name}</dd></div>
              <div><dt>Facilities</dt><dd>{detail.loading ? '…' : properties.facilities || 'Not provided'}</dd></div></dl>
            <div className="detail-description"><h3>Description</h3><p>{detail.loading ? '…' : properties.description || 'Not provided'}</p></div>
            <button className="primary-button" onClick={() => { setFocus({ feature: selected, at: Date.now() }); closeDetails(); }}>View on Map</button>
          </aside>}
        </main>}
      </div>
    </div>
    <NoticeDialog notice={page === 'map' && showNotice ? notice : null} onClose={() => setDismissed(noticeKey)}
      onAction={notice === EMPTY_NOTICE ? () => { setDismissed(noticeKey); clearFilters(); } : notice === LIMIT_NOTICE ? undefined : retry}
      actionLabel={notice === EMPTY_NOTICE ? 'Clear filters' : 'Retry'} />
  </>;
}
