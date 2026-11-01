import { useEffect, useRef } from 'react';

// Prototype error format, shared with additional empty/error states.
export default function NoticeDialog({ notice, onClose, onAction, actionLabel = 'Retry', closeLabel = 'Close' }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!notice) return undefined;
    const previous = document.activeElement;
    const dialog = ref.current;
    dialog.showModal();
    return () => { dialog.close(); if (previous?.isConnected) previous.focus(); };
  }, [notice]);
  if (!notice) return null;
  return <dialog ref={ref} className="notice-dialog" aria-labelledby="notice-title" aria-describedby="notice-description"
    onCancel={event => { event.preventDefault(); onClose(); }}>
    <h2 id="notice-title">{notice.title}</h2>
    <p id="notice-description">{notice.subtitle}</p>
    <div className={`attention-box ${notice.tone || ''}`}><strong>{notice.tone === 'information' ? 'Information' : notice.tone === 'success' ? 'Success' : 'Attention'}</strong><p>{notice.message}</p></div>
    <p>{notice.guidance}</p>
    <div className="dialog-actions">
      {onAction && <button className="primary-button" onClick={onAction} autoFocus>{actionLabel}</button>}
      <button className="secondary-button" onClick={onClose}>{closeLabel}</button>
    </div>
  </dialog>;
}
