import { useEffect, useRef, useState } from 'react';
import Icon from './components/Icon.jsx';
import NoticeDialog from './components/NoticeDialog.jsx';
import ReportDocument from './components/ReportDocument.jsx';
import { REPORT_TYPE, REPORT_SECTIONS, GENERATION_ERROR, GENERATED, reportJSON, validateReport, validateReports } from './reportApi.js';

const draftNotice = { title: 'Draft saved', subtitle: 'The report configuration has been saved.', tone: 'success',
  message: 'This draft is private and has not been published.' };
const initial = () => ({ report_type: REPORT_TYPE, area: null, reporting_period: `Q${Math.floor(new Date().getMonth() / 3) + 1} ${new Date().getFullYear()}`,
  sections: REPORT_SECTIONS.slice(0,4).map(([key]) => key) });

export default function AdminReportsPage() {
  const [config, setConfig] = useState(initial), [options, setOptions] = useState(null), [saved, setSaved] = useState(null), [drafts, setDrafts] = useState([]);
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [error, setError] = useState(''), [notice, setNotice] = useState(null), [revision, setRevision] = useState(0);
  const request = useRef(null), sequence = useRef(0), submission = useRef(null), lastAction = useRef('generate');
  useEffect(() => {
    const controller = new AbortController(); let active = true;
    const timer = setTimeout(() => controller.abort(), 20000); setLoading(true); setError('');
    reportJSON('/api/admin/reports/options/', { signal: controller.signal }).then(async data => {
      if (!active) return;
      if (!Array.isArray(data.areas) || typeof data.csrf_token !== 'string' || typeof data.can_create !== 'boolean') throw new Error('Administrator report options are incomplete.');
      setOptions(data);
      const list = validateReports(await reportJSON('/api/admin/reports/drafts/', { signal: controller.signal }), 1, true);
      if (active) setDrafts(list.results);
    }).catch(problem => { if (active) setError(problem.message); }).finally(() => { clearTimeout(timer); if (active) setLoading(false); });
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [revision]);
  useEffect(() => () => { sequence.current += 1; request.current?.abort(); }, []);
  function edit(update) { setConfig(previous => ({ ...previous, ...update })); setSaved(null); setNotice(null); setError(''); }
  async function save(action) {
    if (busy) return;
    if (!config.reporting_period.trim() || !config.sections.length) { setError('Enter a reporting period and choose at least one section.'); return; }
    const signature = JSON.stringify({ action, config });
    if (submission.current?.signature !== signature) submission.current = { signature, key: crypto.randomUUID() };
    const controller = new AbortController(), current = ++sequence.current; request.current = controller; lastAction.current = action;
    const timer = setTimeout(() => controller.abort(), 20000); setBusy(true); setNotice(null); setError('');
    try {
      const data = await reportJSON(`/api/admin/reports/${action === 'generate' ? 'generate' : 'save-draft'}/`, {
        method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json', 'X-CSRFToken': options.csrf_token },
        body: JSON.stringify({ ...config, request_key: submission.current.key }),
      });
      if (current !== sequence.current) return;
      if (action === 'generate') { setSaved(validateReport(data, data.report_id)); setNotice(GENERATED); }
      else { validateReports({ results: [data], count: 1, page: 1, has_next: false }, 1, true); setNotice(draftNotice); setRevision(n => n + 1); }
      submission.current = null;
    } catch (problem) { if (current === sequence.current) { setError(`${problem.message} A disconnected request may have completed; Retry reuses its request key.`); setNotice(action === 'generate' ? GENERATION_ERROR : { ...GENERATION_ERROR, title: 'Draft could not be saved', subtitle: 'The report configuration could not be saved.' }); } }
    finally { clearTimeout(timer); if (current === sequence.current) setBusy(false); }
  }
  async function reopen(id) {
    setBusy(true); const controller = new AbortController(), current = ++sequence.current; request.current = controller;
    const timer = setTimeout(() => controller.abort(), 20000);
    try { const row = await reportJSON(`/api/admin/reports/drafts/${id}/`, { signal: controller.signal });
      if (current !== sequence.current) return;
      const c = row.configuration;
      if (c?.report_type !== REPORT_TYPE || typeof c.reporting_period !== 'string' || !Array.isArray(c.sections) || !c.sections.every(s => REPORT_SECTIONS.some(([key]) => s === key))) throw new Error('Draft configuration is incomplete.');
      setConfig(c); setSaved(null); submission.current = null; setError('');
    } catch (problem) { if (current === sequence.current) setError(problem.message); }
    finally { clearTimeout(timer); if (current === sequence.current) setBusy(false); }
  }
  return <main className="admin-report-workspace" id="map-content" tabIndex={-1}>
    <section className="dashboard-panel report-configuration"><h2>Report configuration</h2><p className="subtle">Choose the scope and indicators to include.</p>
      {loading && <p role="status" className="subtle">Checking administrator session…</p>}
      {!options && !loading && <div className="inline-notice">{error}<p>Use your existing Django administrator login, then return here.</p><a href="http://127.0.0.1:8000/admin/login/" target="_blank" rel="noreferrer">Admin login</a><button className="text-button" onClick={() => setRevision(n => n + 1)}>Check session</button></div>}
      <fieldset disabled={busy || !options?.can_create} className="report-config-fields">
        <label><span className="field-label">REPORT TYPE</span><select value={config.report_type} onChange={e => edit({ report_type: e.target.value })}><option>{REPORT_TYPE}</option></select></label>
        <label><span className="field-label">ADMINISTRATIVE AREA</span><select value={config.area ?? ''} onChange={e => edit({ area: e.target.value ? Number(e.target.value) : null })}><option value="">All areas</option>{options?.areas.map(area => <option key={area.area_id} value={area.area_id}>{area.area_name}</option>)}</select></label>
        <label><span className="field-label">REPORTING PERIOD</span><input value={config.reporting_period} maxLength={100} onChange={e => edit({ reporting_period: e.target.value })} /></label>
        <span className="field-label">INCLUDE SECTIONS</span>{REPORT_SECTIONS.map(([key, label]) => <label className="report-section-check" key={key}><input type="checkbox" checked={config.sections.includes(key)} onChange={e => edit({ sections: e.target.checked ? [...config.sections, key] : config.sections.filter(s => s !== key) })} />{label}</label>)}
        <div className="report-source-note"><strong>Generated from validated data</strong><span>{saved ? `${saved.snapshot.summary.space_count} saved records` : 'Requires approved records in the database'}</span><span>Distance threshold: 1 km</span></div>
        <p className="subtle">Generate preview creates a published snapshot visible to public users. Save draft stays private. The period is a label; it does not select historical data.</p>
        <button className="primary-button" disabled={Boolean(saved)} onClick={() => save('generate')}><Icon name="report" size={16} />Generate preview</button>
        <button className="secondary-button" onClick={() => save('draft')}>Save draft</button>
      </fieldset>
      {options && !options.can_create && <p className="inline-notice">This account can view reports but does not have permission to create them.</p>}
      {error && options && <p className="inline-notice" role="alert">{error}</p>}
      {!!drafts.length && <div className="saved-drafts"><h3>Saved drafts</h3><p className="subtle">Latest nine drafts. Opening restores settings; generation creates a separate published report.</p>{drafts.map(row => <button className="text-button" key={row.report_id} disabled={busy} onClick={() => reopen(row.report_id)}>{row.title} · Open</button>)}</div>}
    </section>
    <section className="report-preview"><div className="report-preview-heading"><h2>Report preview</h2><button className="secondary-button" disabled={!saved || busy} onClick={() => window.print()}><Icon name="download" size={16} />Export PDF</button></div>
      <p className="subtle no-print">Export PDF opens the browser print dialog. Choose Save as PDF. No file is created until you confirm.</p>
      {saved ? <div className="print-report"><ReportDocument snapshot={saved.snapshot} /></div> : <div className="report-preview-empty">{busy ? 'Preparing report…' : 'Configure the report and select Generate preview.'}</div>}
    </section>
    <NoticeDialog notice={notice} onClose={() => setNotice(null)} actionLabel={notice === GENERATED ? 'View Report' : 'Try Again'}
      onAction={notice === GENERATED ? () => { setNotice(null); document.querySelector('.report-preview')?.scrollIntoView({ behavior: 'smooth' }); } : notice?.tone === 'success' ? undefined : () => save(lastAction.current)} />
  </main>;
}
