import { useEffect, useRef, useState } from 'react';
import { formatArea, getJSON } from '../mapApi.js';
import Icon from './Icon.jsx';
import NoticeDialog from './NoticeDialog.jsx';

const ERROR = { title: 'Details could not be loaded', subtitle: 'Unable to display the green-space details.',
  message: 'There was a problem loading the selected green space.', guidance: 'Please check the connection and try again.' };
export default function NearbyDetails({ feature, onClose, onView }) {
  const heading = useRef(null);
  const [state, setState] = useState({ data: null, loading: true, error: false });
  const [revision, setRevision] = useState(0), [dismissed, setDismissed] = useState(false);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, [feature.id]);
  useEffect(() => {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort('timeout'), 15000);
    setState({ data: null, loading: true, error: false }); setDismissed(false);
    getJSON(`/api/public/green-spaces/${feature.id}/`, { signal: controller.signal }).then(data => {
      if (data.id !== feature.id || data.type !== 'Feature' || !data.properties) throw new Error('Invalid detail');
      if (!controller.signal.aborted) setState({ data, loading: false, error: false });
    }).catch(() => { if (!controller.signal.aborted || controller.signal.reason === 'timeout') setState({ data: null, loading: false, error: true }); })
      .finally(() => clearTimeout(timer));
    return () => { clearTimeout(timer); controller.abort(); };
  }, [feature.id, revision]);
  const props = state.data?.id === feature.id ? state.data.properties : feature.properties;
  return <><aside className="details-drawer" role="dialog" aria-modal="false" aria-labelledby="nearby-details-heading"
    onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); onClose(); } }}>
    <div className="details-heading"><h2 id="nearby-details-heading" ref={heading} tabIndex={-1}>Green-Space Details</h2>
      <button className="plain-close" aria-label="Close green-space details" onClick={onClose}><Icon name="close" size={16} /></button></div>
    <div className="detail-image-placeholder" aria-hidden="true"><div /></div>
    {state.loading && <p className="subtle" role="status">Loading details…</p>}
    <dl className="detail-facts"><div><dt>Name</dt><dd>{props.name}</dd></div><div><dt>Type</dt><dd>{props.category_name}</dd></div>
      <div><dt>Area</dt><dd>{formatArea(props.area_size)}</dd></div><div><dt>District</dt><dd>{props.area_name}</dd></div>
      <div><dt>Facilities</dt><dd>{state.loading ? '…' : props.facilities || 'Not provided'}</dd></div></dl>
    <div className="detail-description"><h3>Description</h3><p>{state.loading ? '…' : props.description || 'Not provided'}</p></div>
    <button className="primary-button" onClick={() => onView(feature)}>View on Map</button>
  </aside><NoticeDialog notice={state.error && !dismissed ? ERROR : null} onClose={() => setDismissed(true)} onAction={() => setRevision(value => value + 1)} /></>;
}
