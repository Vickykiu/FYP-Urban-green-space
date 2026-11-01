import { test } from 'node:test';
import assert from 'node:assert/strict';
import { publicQuery, searchNearby } from '../src/nearbyApi.js';

const response = (data, ok = true) => ({ ok, status: ok ? 200 : 503, json: async () => data });
const feature = (id, distance) => ({ type: 'Feature', id, geometry: { type: 'Point', coordinates: [101.6, 3.1] },
  properties: { name: 'TEST park', distance_m: distance } });
const collection = (features, has_next = false, count = features.length) => ({ type: 'FeatureCollection', features,
  count, has_next, radius_m: 1000, distance_method: 'spheroidal_straight_line_to_geometry' });
const origin = { latitude: 3.08, longitude: 101.6, label: 'Private user label' };

test('coordinates and private labels do not go into URLs; CSRF is attached', async () => {
  const fetcher = async (url, options) => {
    assert.ok(!url.includes('?')); assert.ok(!url.includes('101.6'));
    if (url.endsWith('/options/')) return response({ csrf_token: 'test-token' });
    assert.equal(options.method, 'POST'); assert.equal(options.headers['X-CSRFToken'], 'test-token');
    assert.equal(options.credentials, 'same-origin');
    const data = JSON.parse(options.body);
    assert.deepEqual(Object.keys(data).sort(), ['latitude', 'longitude', 'page', 'radius_m']);
    return response(collection([feature(1, 20)]));
  };
  assert.equal((await searchNearby(origin, 1000, { fetcher })).count, 1);
});
test('nearby results follow pages and have deterministic distance ordering', async () => {
  const fetcher = async (url, options) => url.endsWith('/options/') ? response({ csrf_token: 'token' })
    : response(JSON.parse(options.body).page === 1 ? collection([feature(3, 40), feature(2, 20)], true, 3)
      : collection([feature(1, 20)], false, 3));
  assert.deepEqual((await searchNearby(origin, 1000, { fetcher })).features.map(f => f.id), [1, 2, 3]);
});
test('failure is not converted into a successful empty result', async () => {
  await assert.rejects(publicQuery('/api/public/nearby/', {}, { csrfToken: 'token',
    fetcher: async () => response({ code: 'study_area_unavailable', error: 'private SQL details' }, false) }), /district data is not ready/);
});
test('invalid or outside-radius result is rejected', async () => {
  for (const distance of [NaN, -1, 1001, '500']) {
    const fetcher = async url => response(url.endsWith('/options/') ? { csrf_token: 'token' } : collection([feature(1, distance)]));
    await assert.rejects(searchNearby(origin, 1000, { fetcher }), /outside the requested radius/);
  }
});
test('empty result is a valid success with count zero', async () => {
  const fetcher = async url => response(url.endsWith('/options/') ? { csrf_token: 'token' } : collection([]));
  assert.equal((await searchNearby(origin, 1000, { fetcher })).count, 0);
});
test('cancellation signal is forwarded to every request', async () => {
  const controller = new AbortController(); controller.abort();
  const fetcher = async (url, options) => { assert.equal(options.signal, controller.signal); throw new DOMException('Aborted', 'AbortError'); };
  await assert.rejects(searchNearby(origin, 1000, { fetcher, signal: controller.signal }), { name: 'AbortError' });
});
test('automatic pagination is bounded and reports a limit', async () => {
  let pages = 0;
  const fetcher = async url => url.endsWith('/options/') ? response({ csrf_token: 'token' })
    : response(collection([feature(++pages, 5)], true, 50));
  const result = await searchNearby(origin, 1000, { fetcher });
  assert.equal(pages, 10); assert.equal(result.limited, true);
});
