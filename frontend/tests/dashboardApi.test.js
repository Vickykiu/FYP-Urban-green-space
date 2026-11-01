import { test } from 'node:test';
import assert from 'node:assert/strict';
import { dashboardFilters, validateDashboard, loadDashboard, DASHBOARD_ERROR, percentLabel } from '../src/dashboardApi.js';

function result(filters = { area: null, category: null }) {
  const metrics = { space_count: 2, point_count: 1, green_area_ha: 1.5, area_status: 'partial', zone_area_ha: 100,
    covered_land_ha: 60, coverage_percentage: 60, population_covered: null, population_gap: null, planning_gaps: null, baseline_change_percentage: null };
  return { filters, radius_m: 1000, coverage_basis: 'land_area_within_park_buffers', summary: { ...metrics },
    options: { areas: [{ area_id: 1, area_name: 'TEST district', area_type: 'District' }], categories: [{ category_id: 2, category_name: 'TEST park' }] },
    areas: [{ area_id: 1, area_name: 'TEST district', area_type: 'District', ...metrics }],
    categories: [{ category_id: 2, category_name: 'TEST park', space_count: 2 }], priority_areas: [], priority_status: 'unavailable' };
}
const response = data => ({ ok: true, json: async () => data });

test('dashboard filter contract rejects hidden or invalid parameters', () => {
  assert.deepEqual(dashboardFilters({ area: '', category: '2' }), { area: null, category: 2 });
  for (const filters of [{ area: false }, { area: [] }, { area: '1.5' }, { area: 0 }, { category: Infinity }, { radius: 500 }, { area: '2147483648' }]) {
    assert.throws(() => dashboardFilters(filters), /Invalid/);
  }
});
test('dashboard requests only public filter IDs and forwards cancellation', async () => {
  const controller = new AbortController();
  const data = await loadDashboard({ area: '1', category: '2' }, { signal: controller.signal, fetcher: async (url, options) => {
    assert.equal(url, '/api/public/dashboard/?area=1&category=2'); assert.equal(options.signal, controller.signal);
    assert.equal(options.cache, 'no-store'); assert.equal(options.body, undefined);
    return response(result({ area: 1, category: 2 }));
  } });
  assert.equal(data.summary.coverage_percentage, 60);
});
test('land coverage is distinct from unknown population and priority', () => {
  assert.equal(validateDashboard(result()).summary.population_covered, null);
  for (const mutate of [d => { d.coverage_basis = 'population'; }, d => { d.summary.population_gap = 0; },
    d => { d.priority_areas = [{ priority: 'High' }]; }, d => { d.summary.baseline_change_percentage = 4.2; }]) {
    const data = result(); mutate(data); assert.throws(() => validateDashboard(data), /inconsistent/);
  }
});
test('zero records can be valid without inventing a filled category chart', () => {
  const data = result(); data.categories[0].space_count = 0;
  for (const row of [data.summary, ...data.areas]) Object.assign(row, { space_count: 0, point_count: 0, green_area_ha: 0,
    area_status: 'complete', covered_land_ha: 0, coverage_percentage: 0 });
  assert.equal(validateDashboard(data).summary.space_count, 0);
});
test('point-only footprint is unavailable while buffer coverage is measurable', () => {
  const data = result();
  for (const row of [data.summary, ...data.areas]) Object.assign(row, { point_count: 2, green_area_ha: null, area_status: 'unavailable' });
  assert.equal(validateDashboard(data).summary.coverage_percentage, 60);
  data.summary.green_area_ha = 0; assert.throws(() => validateDashboard(data), /inconsistent/);
});
test('wrong filters, inconsistent totals, duplicate IDs and invalid metrics fail closed', () => {
  for (const mutate of [d => { d.filters.area = 1; }, d => { d.categories[0].space_count = 3; },
    d => { d.areas.push(d.areas[0]); }, d => { d.summary.coverage_percentage = 101; }, d => { d.summary.zone_area_ha = 0; },
    d => { d.summary.covered_land_ha = 59; }, d => { d.summary.green_area_ha = Infinity; }, d => { d.options.areas = []; }]) {
    const data = result(); mutate(data); assert.throws(() => validateDashboard(data), /inconsistent/);
  }
});
test('HTTP failures and invalid JSON are not successful zero results', async () => {
  await assert.rejects(loadDashboard({}, { fetcher: async () => ({ ok: false }) }), /cannot be displayed/);
  await assert.rejects(loadDashboard({}, { fetcher: async () => ({ ok: true, json: async () => { throw new Error(); } }) }), /valid dashboard/);
  await assert.rejects(loadDashboard({ area: 'bad' }, { fetcher: () => assert.fail('Must not fetch') }), /Invalid/);
});
test('dashboard labels and failure text follow the reference', () => {
  assert.equal(percentLabel(0), '0%'); assert.equal(percentLabel(null), 'Unavailable');
  assert.equal(DASHBOARD_ERROR.title, 'Unable to load dashboard');
  assert.equal(DASHBOARD_ERROR.message, 'Please try again. If the problem continues, check the available dataset.');
});
