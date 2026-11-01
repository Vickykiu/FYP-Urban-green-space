import { useEffect, useState } from 'react';
import { getJSON, loadCollection } from './mapApi.js';

export function useMapData(endpoint, params, enabled, revision) {
  const key = JSON.stringify(params);
  const [state, setState] = useState({ features: [], count: null, limited: false, loading: true, error: '' });
  useEffect(() => {
    const controller = new AbortController();
    if (!enabled) {
      setState({ features: [], count: null, limited: false, loading: false, error: '' });
      return () => controller.abort();
    }
    setState({ features: [], count: null, limited: false, loading: true, error: '' });
    const timer = setTimeout(async () => {
      const timeout = setTimeout(() => controller.abort('timeout'), 20000);
      try {
        const result = await loadCollection(endpoint, JSON.parse(key), { signal: controller.signal });
        if (!controller.signal.aborted) setState({ ...result, loading: false, error: '' });
      } catch (error) {
        if (!controller.signal.aborted || controller.signal.reason === 'timeout') {
          setState({ features: [], count: null, limited: false, loading: false,
            error: controller.signal.reason === 'timeout' ? 'Map data took too long to load. Please retry.'
              : error.message || 'Map data could not be loaded.' });
        }
      } finally { clearTimeout(timeout); }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [endpoint, key, enabled, revision]);
  return state;
}

export function useMapOptions(revision, enabled = true) {
  const [state, setState] = useState({ data: null, loading: true, error: '' });
  useEffect(() => {
    const controller = new AbortController();
    if (!enabled) {
      setState({ data: null, loading: false, error: '' });
      return () => controller.abort();
    }
    const timeout = setTimeout(() => controller.abort('timeout'), 15000);
    setState({ data: null, loading: true, error: '' });
    getJSON('/api/public/map-options/', { signal: controller.signal }).then(data => {
      if (!Array.isArray(data.categories)) throw new Error('Category information is unavailable.');
      if (!controller.signal.aborted) setState({ data, loading: false, error: '' });
    }).catch(() => {
      if (!controller.signal.aborted || controller.signal.reason === 'timeout') {
        setState({ data: null, loading: false, error: 'Categories are unavailable until the database is connected.' });
      }
    }).finally(() => clearTimeout(timeout));
    return () => { clearTimeout(timeout); controller.abort(); };
  }, [revision, enabled]);
  return state;
}
