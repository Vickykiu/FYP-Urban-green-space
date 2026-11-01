import test from 'node:test';
import assert from 'node:assert/strict';
import { getJSON, loadCollection, formatArea } from '../src/mapApi.js';

const feature = id => ({ type: 'Feature', id, geometry: { type: 'Point', coordinates: [101.6, 3.1] }, properties: { name: 'TEST' } });
const response = data => ({ ok: true, json: async () => data });
test('preserves GeoJSON and follows all pages', async () => {
  const calls = [];
  const result = await loadCollection('/api/public/green-spaces/', { q: 'park & garden' }, { fetcher: async url => {
    calls.push(url);
    return response({ type: 'FeatureCollection', count: 2, has_next: calls.length === 1, features: [feature(calls.length)] });
  } });
  assert.equal(result.features.length, 2); assert.equal(result.limited, false);
  assert.equal(new URL(calls[1], 'http://test').searchParams.get('q'), 'park & garden');
  assert.equal(new URL(calls[1], 'http://test').searchParams.get('page'), '2');
});
test('honestly marks results limited after ten pages', async () => {
  let calls = 0;
  const result = await loadCollection('/test', {}, { fetcher: async () => {
    calls += 1;
    return response({ type: 'FeatureCollection', count: 20, has_next: true, features: [feature(calls)] });
  } });
  assert.equal(calls, 10); assert.equal(result.limited, true);
});
test('deduplicates records that shift between pages', async () => {
  let calls = 0;
  const result = await loadCollection('/test', {}, { fetcher: async () => response({ type: 'FeatureCollection', count: 1,
    has_next: ++calls === 1, features: [feature(1)] }) });
  assert.equal(result.features.length, 1);
});
test('empty dataset is not a network failure', async () => {
  const result = await loadCollection('/test', {}, { fetcher: async () => response({ type: 'FeatureCollection', count: 0, has_next: false, features: [] }) });
  assert.deepEqual(result, { features: [], count: 0, limited: false });
});
test('HTTP errors do not become empty successful data', async () => {
  await assert.rejects(getJSON('/test', { fetcher: async () => ({ ok: false, status: 503 }) }), /unavailable/);
});
test('invalid JSON is reported clearly', async () => {
  await assert.rejects(getJSON('/test', { fetcher: async () => ({ ok: true, json: async () => { throw new Error('HTML'); } }) }), /valid map data/);
});
test('rejects invalid collection shape', async () => {
  await assert.rejects(loadCollection('/test', {}, { fetcher: async () => response({ features: [] }) }), /unexpected/);
});
test('cancellation reaches the request', async () => {
  const controller = new AbortController(); controller.abort();
  await assert.rejects(getJSON('/test', { signal: controller.signal, fetcher: async (url, opts) => {
    opts.signal.throwIfAborted();
  } }), { name: 'AbortError' });
});
test('area formatting distinguishes missing from zero', () => {
  assert.equal(formatArea(null), 'Not provided'); assert.equal(formatArea('0'), '0 ha');
  assert.equal(formatArea('1.2500'), '1.25 ha'); assert.equal(formatArea('NaN'), 'Not provided');
});
