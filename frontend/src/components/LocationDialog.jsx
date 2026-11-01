import { useEffect, useRef, useState } from 'react';
import GreenMap from './GreenMap.jsx';
import Icon from './Icon.jsx';
import district from '../../../data/petaling-district.json';
import { coordinateLabel, currentLocation, parseCoordinates, validCoordinates, withinDistrict } from '../location.js';
import { publicQuery } from '../nearbyApi.js';

const EMPTY = [];
export default function LocationDialog({ initial, onConfirm, onCancel }) {
  const dialog = useRef(null), request = useRef(null), generation = useRef(0);
  const [text, setText] = useState(initial?.label || ''), [point, setPoint] = useState(initial || null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [candidates, setCandidates] = useState([]);
  const [view, setView] = useState(initial || null);
  useEffect(() => {
    const previous = document.activeElement, element = dialog.current;
    element.showModal();
    return () => { generation.current += 1; request.current?.abort(); element.close(); previous?.isConnected && previous.focus({ preventScroll: true }); };
  }, []);
  function invalidate() { generation.current += 1; request.current?.abort(); setBusy(false); setCandidates([]); }
  function choose(location) {
    invalidate();
    if (!validCoordinates(location) || !withinDistrict(location)) {
      setPoint(null); setError('Select a starting location inside Petaling District.'); return;
    }
    setPoint(location); setText(location.label || coordinateLabel(location)); setView({ ...location, at: Date.now() }); setError('');
  }
  async function find(event) {
    event?.preventDefault(); invalidate(); setPoint(null); setError('');
    const coordinates = parseCoordinates(text);
    if (coordinates) { choose(coordinates); return; }
    if (text.trim().length < 2) { setError('Please enter a valid address or select another point on the map.'); return; }
    const current = generation.current, controller = new AbortController(); request.current = controller;
    const timeout = setTimeout(() => controller.abort('timeout'), 15000);
    setBusy(true);
    try {
      const data = await publicQuery('/api/public/locations/search/', { q: text.trim() }, { signal: controller.signal });
      if (current !== generation.current) return;
      if (!Array.isArray(data.results) || data.results.length > 10 || !data.results.every(validCoordinates)) throw new Error('Location results could not be read.');
      if (!data.results.length) setError('No matching administrator-maintained place was found. Street-address lookup is not configured; select a point on the map.');
      else setCandidates(data.results);
    } catch (problem) {
      if (current === generation.current) setError(controller.signal.reason === 'timeout' ? 'Location search took too long. Please try again.' : problem.message);
    } finally { clearTimeout(timeout); if (current === generation.current) setBusy(false); }
  }
  async function locate() {
    invalidate(); setPoint(null); setError(''); setBusy(true);
    const current = generation.current;
    try { const location = await currentLocation(); if (current === generation.current) choose(location); }
    catch (problem) { if (current === generation.current) setError(problem.message); }
    finally { if (current === generation.current) setBusy(false); }
  }
  return <dialog ref={dialog} className={`location-dialog ${error ? 'location-error-dialog' : ''}`}
    aria-labelledby="location-title" aria-describedby="location-subtitle" onCancel={event => { event.preventDefault(); onCancel(); }}>
    <h2 id="location-title">Select Location</h2>
    <p id="location-subtitle">{error ? 'The selected location could not be identified.' : 'Choose a location for nearby search or accessibility analysis.'}</p>
    {error ? <>
      <label className="field-label" htmlFor="invalid-location">Address or place</label>
      <input id="invalid-location" className="location-input invalid" readOnly value={text} aria-invalid="true" aria-describedby="location-error-message" />
      <p className="field-error">Please enter a valid value.</p>
      <div className="attention-box" id="location-error-message" role="alert"><strong>Location not found</strong>
        <p>Please enter a valid address or select another point on the map.</p><p>{error}</p></div>
      <button className="secondary-button back-button" onClick={() => setError('')}>Back</button>
    </> : <>
      <div className="location-columns">
        <div>
          <form onSubmit={find}>
            <label className="field-label" htmlFor="address-place">Address or place</label>
            <div className="location-input-wrap"><input id="address-place" className="location-input" autoFocus maxLength={150}
              placeholder="Enter an address or place" value={text}
              onChange={event => { invalidate(); setText(event.target.value); setPoint(null); }} />
              <button type="submit" aria-label="Find location" title="Find an uploaded place name or enter latitude, longitude" disabled={busy}><Icon name="search" size={16} /></button></div>
          </form>
          {candidates.length > 0 && <ul className="location-candidates" aria-label="Matching places">{candidates.map(item => <li key={item.id}>
            <button onClick={() => choose(item)}>{item.label}<small>{coordinateLabel(item)}</small></button></li>)}</ul>}
          <h3>Selected Location</h3>
          <div className="chosen-location" aria-live="polite"><strong>{point?.label || 'No location selected'}</strong>
            <span>{point ? coordinateLabel(point) : 'Choose a point on the map.'}</span>
            {Number.isFinite(point?.accuracy_m) && <span>Device accuracy: approximately {Math.round(point.accuracy_m)} m</span>}</div>
          <p className="location-tip">Tip: enter an address or choose a point directly on the map.</p>
          <button className="text-button current-location" onClick={locate} disabled={busy}><Icon name="target" size={15} />Use current location</button>
          {busy && <p className="subtle" role="status">Finding location…</p>}
        </div>
        <div className="location-mini-map"><GreenMap greens={EMPTY} boundaries={district.features} seedVisible origin={point}
          onPick={choose} searchView={view} /></div>
      </div>
      <div className="location-actions"><button className="primary-button" disabled={!point || busy}
        onClick={() => { if (validCoordinates(point) && withinDistrict(point)) onConfirm(point); }}>Confirm Location</button>
        <button className="secondary-button" onClick={onCancel}>Cancel</button></div>
    </>}
  </dialog>;
}
