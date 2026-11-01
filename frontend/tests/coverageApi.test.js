import { test } from 'node:test';
import assert from 'node:assert/strict';
import { analyseCoverage, validateCoverage, formatCoverageArea, ANALYSIS_ERROR } from '../src/coverageApi.js';

const origin = { latitude: 3.08, longitude: 101.6, label: 'Private location label' };
const shape = { type: 'Polygon', coordinates: [[[101.59,3.07],[101.61,3.07],[101.61,3.09],[101.59,3.07]]] };
const response = (data, ok = true) => ({ ok, json: async () => data });
function result(radius = 1000) {
  return { method: 'distance_buffer', radius_m: radius,
    coverage: { type: 'FeatureCollection', features: [...new Set([500, 1000, 2000, radius])].map(r => ({
      type: 'Feature', geometry: structuredClone(shape), properties: { radius_m: r, selected: r === radius, coverage_area_m2: 1000000 } })) },
    metrics: { population_covered: null, population_percentage: null, population_status: 'unavailable',
      green_spaces_reached: 0, change_from_500_m: 0, total_accessible_area_ha: 0, accessible_area_percentage: 0,
      coverage_area_ha: 100, point_records_without_footprint: 0, area_status: 'complete' },
    green_spaces: { type: 'FeatureCollection', features: [], count: 0, limited: false } };
}

test('analysis uses POST and CSRF without exposing location in URL or label', async () => {
  const fetcher = async (url, options) => {
    assert.ok(!url.includes('?'));
    if (url.endsWith('/options/')) return response({ csrf_token: 'test-token' });
    assert.equal(url, '/api/public/accessibility/'); assert.equal(options.method, 'POST');
    assert.equal(options.headers['X-CSRFToken'], 'test-token');
    assert.deepEqual(JSON.parse(options.body), { latitude: 3.08, longitude: 101.6, radius_m: 1000 });
    return response(result());
  };
  assert.equal((await analyseCoverage(origin, '1000', { fetcher })).metrics.green_spaces_reached, 0);
});
test('empty valid coverage has real zeros but no fabricated population', () => {
  assert.equal(validateCoverage(result(), 1000).metrics.total_accessible_area_ha, 0);
  const data = result(); data.metrics.population_covered = 18420;
  assert.throws(() => validateCoverage(data, 1000), /inconsistent/);
});
test('selected and custom distance bands must match the request', () => {
  assert.equal(validateCoverage(result(750), 750).coverage.features.length, 4);
  const data = result(); data.coverage.features[0].properties.selected = true;
  assert.throws(() => validateCoverage(data, 1000), /inconsistent/);
  assert.throws(() => validateCoverage(result(), 2000), /inconsistent/);
});
test('unsafe geometry, incomplete rings and duplicated bands are rejected before Leaflet', () => {
  for (const mutate of [d => { d.coverage.features[0].geometry.coordinates[0][0][0] = Infinity; },
    d => { d.coverage.features[0].geometry.coordinates[0].pop(); },
    d => { d.coverage.features[1] = d.coverage.features[0]; }]) {
    const data = result(); mutate(data); assert.throws(() => validateCoverage(data, 1000), /inconsistent/);
  }
});
test('point-only results do not claim zero accessible area', () => {
  const data = result();
  Object.assign(data.metrics, { green_spaces_reached: 1, point_records_without_footprint: 1,
    area_status: 'unavailable', total_accessible_area_ha: null, accessible_area_percentage: null });
  data.green_spaces.count = 1; data.green_spaces.features = [{ type: 'Feature', id: 1,
    geometry: { type: 'Point', coordinates: [101.6,3.08] }, properties: { name: 'TEST', distance_m: 0 } }];
  assert.equal(validateCoverage(data, 1000).metrics.total_accessible_area_ha, null);
  data.metrics.total_accessible_area_ha = 0;
  assert.throws(() => validateCoverage(data, 1000), /inconsistent/);
});
test('invalid metrics and misleading truncation are rejected', () => {
  for (const mutate of [d => { d.metrics.total_accessible_area_ha = -1; },
    d => { d.metrics.accessible_area_percentage = 101; }, d => { d.green_spaces.limited = true; },
    d => { d.metrics.green_spaces_reached = 2; }]) {
    const data = result(); mutate(data); assert.throws(() => validateCoverage(data, 1000), /inconsistent/);
  }
});
test('invalid analysis settings never trigger network requests', async () => {
  const fetcher = () => assert.fail('No request expected');
  for (const distance of [99, 10001, 500.5, '', false]) await assert.rejects(analyseCoverage(origin, distance, { fetcher }), /valid location/);
});
test('analysis errors are not empty successful results and retain cancellation', async () => {
  const controller = new AbortController();
  await assert.rejects(analyseCoverage(origin, 1000, { signal: controller.signal, csrfToken: 'token', fetcher: async (url, options) => {
    assert.equal(options.signal, controller.signal);
    return response({ code: 'green_space_data_unavailable', error: 'private SQL' }, false);
  } }), /import approved CSV/);
});
test('area labels distinguish zero from unavailable and error wording matches prototype', () => {
  assert.equal(formatCoverageArea(0), '0 ha'); assert.equal(formatCoverageArea(null), 'Unavailable');
  assert.equal(ANALYSIS_ERROR.title, 'Analysis failed');
  assert.equal(ANALYSIS_ERROR.message, 'The selected location or required spatial data is unavailable.');
});
