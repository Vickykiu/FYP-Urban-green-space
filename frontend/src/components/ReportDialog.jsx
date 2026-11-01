import { useEffect, useRef } from 'react';
import ReportDocument from './ReportDocument.jsx';
import { percentLabel } from '../dashboardApi.js';

export default function ReportDialog({ report, onClose }) {
  const ref = useRef(null);
  useEffect(() => { const previous = document.activeElement, dialog = ref.current; dialog.showModal();
    return () => { dialog.close(); if (previous?.isConnected) previous.focus(); }; }, []);
  return <dialog ref={ref} className="report-dialog" aria-labelledby="report-dialog-title" onCancel={event => { event.preventDefault(); onClose(); }}>
    <h2 id="report-dialog-title">Accessibility Coverage Report</h2><p className="subtle">Generated planning-support report • saved data snapshot</p>
    <section className="report-summary-box"><h3>Summary</h3><p>{percentLabel(report.snapshot.summary.coverage_percentage)} of the selected planning area's land is within the configured 1 km coverage distance.</p><p>Priority gaps are not assessed because the required population data and criteria are unavailable.</p></section>
    <div className="report-dialog-statistics"><div className="report-coverage-illustration" aria-hidden="true"><div><div><div /></div></div></div>
      <section><h3>Coverage statistics</h3>{['High accessibility', 'Medium accessibility', 'Low accessibility'].map(label => <div className="report-class-stat" key={label}><span>{label}</span><strong>Unavailable</strong></div>)}
      <p className="subtle">Accessibility classes are not configured; no percentages are invented. The summary above measures land coverage, not population coverage.</p></section></div>
    <details className="report-full-details"><summary>Report details</summary><ReportDocument snapshot={report.snapshot} compact /></details>
    <div className="dialog-actions"><button className="secondary-button" onClick={onClose}>Close</button></div>
  </dialog>;
}
