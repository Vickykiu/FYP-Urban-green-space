const count = value => Number.isSafeInteger(value) && value >= 0;
const positiveId = value => Number.isSafeInteger(value) && value > 0;
const number = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
const percent = value => number(value) && value <= 100;
const unique = (rows, key) => new Set(rows.map(row => row?.[key])).size === rows.length;

export function dashboardFilters(filters = {}) {
  if (!filters || typeof filters !== 'object' || Array.isArray(filters)
    || Object.keys(filters).some(key => !['area', 'category'].includes(key))) throw new Error('Invalid dashboard filters.');
  const result = {};
  for (const key of ['area', 'category']) {
    const value = filters[key];
    if (value === '' || value == null) { result[key] = null; continue; }
    if ((typeof value !== 'string' || !/^[0-9]{1,10}$/.test(value)) && typeof value !== 'number') throw new Error('Invalid dashboard filters.');
    if (!positiveId(Number(value)) || Number(value) > 2147483647) throw new Error('Invalid dashboard filters.');
    result[key] = Number(value);
  }
  return result;
}

function validMetrics(m) {
  if (!m || !count(m.space_count) || !count(m.point_count) || m.point_count > m.space_count
      || !number(m.zone_area_ha) || m.zone_area_ha === 0 || !number(m.covered_land_ha)
      || m.covered_land_ha > m.zone_area_ha + 0.000001 || !percent(m.coverage_percentage)
      || Math.abs(m.coverage_percentage - m.covered_land_ha / m.zone_area_ha * 100) > 0.0001
      || [m.population_covered, m.population_gap, m.planning_gaps, m.baseline_change_percentage].some(v => v !== null)) return false;
  const expected = m.point_count === 0 ? 'complete' : m.point_count === m.space_count ? 'unavailable' : 'partial';
  return m.area_status === expected && (expected === 'unavailable' ? m.green_area_ha === null
    : number(m.green_area_ha) && m.green_area_ha <= m.zone_area_ha + 0.000001);
}

export function validateDashboard(data, filters = {}) {
  const expected = dashboardFilters(filters);
  const invalid = () => { throw new Error('The dashboard returned incomplete or inconsistent information. Please retry.'); };
  if (data?.coverage_basis !== 'land_area_within_park_buffers' || data.radius_m !== 1000
      || data.filters?.area !== expected.area || data.filters?.category !== expected.category
      || !validMetrics(data.summary) || data.priority_status !== 'unavailable'
      || !Array.isArray(data.priority_areas) || data.priority_areas.length !== 0) invalid();
  const areas = data.options?.areas, categories = data.options?.categories;
  if (!Array.isArray(areas) || !areas.length || !unique(areas, 'area_id')
      || !areas.every(a => positiveId(a?.area_id) && typeof a.area_name === 'string' && a.area_name.trim() && typeof a.area_type === 'string')
      || !Array.isArray(categories) || !categories.length || !unique(categories, 'category_id')
      || !categories.every(c => positiveId(c?.category_id) && typeof c.category_name === 'string' && c.category_name.trim())) invalid();
  if ((expected.area !== null && !areas.some(a => a.area_id === expected.area))
      || (expected.category !== null && !categories.some(c => c.category_id === expected.category))) invalid();
  const areaIds = areas.filter(a => expected.area === null || a.area_id === expected.area).map(a => a.area_id);
  const categoryIds = categories.filter(c => expected.category === null || c.category_id === expected.category).map(c => c.category_id);
  if (!Array.isArray(data.areas) || data.areas.length !== areaIds.length || !unique(data.areas, 'area_id')
      || !data.areas.every(a => areaIds.includes(a?.area_id) && typeof a.area_name === 'string' && typeof a.area_type === 'string' && validMetrics(a))
      || !Array.isArray(data.categories) || data.categories.length !== categoryIds.length || !unique(data.categories, 'category_id')
      || !data.categories.every(c => categoryIds.includes(c?.category_id) && typeof c.category_name === 'string' && count(c.space_count))
      || data.categories.reduce((sum, c) => sum + c.space_count, 0) !== data.summary.space_count) invalid();
  return data;
}

export async function loadDashboard(filters = {}, { signal, fetcher = fetch } = {}) {
  const normalized = dashboardFilters(filters);
  const params = new URLSearchParams(Object.entries(normalized).filter(([, value]) => value !== null));
  const response = await fetcher(`/api/public/dashboard/${params.size ? `?${params}` : ''}`, { signal, cache: 'no-store', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('Dashboard information cannot be displayed. Check the backend connection and available dataset.');
  let data;
  try { data = await response.json(); } catch { throw new Error('The server did not return valid dashboard information.'); }
  return validateDashboard(data, normalized);
}

export const DASHBOARD_ERROR = {
  title: 'Unable to load dashboard', subtitle: 'The planning dashboard data could not be retrieved.',
  message: 'Please try again. If the problem continues, check the available dataset.',
};
export const DASHBOARD_COLORS = ['#10b981', '#14b8a6', '#3b82f6', '#f59e0b', '#8b5cf6', '#64748b'];
export function percentLabel(value) { return value == null ? 'Unavailable' : `${value.toLocaleString('en-MY', { maximumFractionDigits: 1 })}%`; }
