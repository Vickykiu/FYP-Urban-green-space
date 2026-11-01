import { validateDashboard } from './dashboardApi.js';

export const REPORT_TYPE = 'Accessibility planning report';
export const REPORT_SECTIONS = [['executive_summary', 'Executive summary'], ['coverage_indicators', 'Coverage indicators'],
  ['priority_gap', 'Priority gap analysis'], ['inventory', 'Green-space inventory'], ['methodology', 'Methodology notes']];
export const NO_REPORT = { title: 'No report available', subtitle: 'There is no generated report matching the current selection.',
  message: 'The administrator must generate and publish a planning report before it can be viewed.', tone: 'information' };
export const REPORT_ERROR = { title: 'Unable to load report', subtitle: 'The planning report could not be retrieved.',
  message: 'Please try again. If the problem continues, check the available dataset.' };
export const GENERATION_ERROR = { title: 'Generation failed', subtitle: 'The planning report could not be generated.',
  message: 'Required green-space or accessibility data is unavailable.', guidance: 'Check the selected criteria and try again.' };
export const GENERATED = { title: 'Report generated', subtitle: 'The planning report has been successfully created.',
  message: 'The report is now available for viewing by users.', guidance: 'Report: Accessibility Planning Report', tone: 'success' };

export async function reportJSON(url, { signal, fetcher = fetch, ...options } = {}) {
  const response = await fetcher(url, { ...options, signal, cache: 'no-store', headers: { Accept: 'application/json', ...options.headers } });
  if (!response.ok) {
    const error = new Error(response.status === 401 ? 'Administrator login is required.' : response.status === 403 ? 'Report permission or CSRF verification failed. Check your administrator session.'
      : response.status === 404 ? 'No report available' : response.status === 409 ? 'This request may already be saved. Retry without changing the configuration.' : 'Report data is unavailable. Please retry.');
    error.status = response.status; throw error;
  }
  try { return await response.json(); } catch { throw new Error('The server did not return valid report data.'); }
}
function metadata(row, allowDraft = false) {
  return Number.isSafeInteger(row?.report_id) && row.report_id > 0 && typeof row.title === 'string'
    && typeof row.area_name === 'string' && typeof row.reporting_period === 'string' && row.report_type === REPORT_TYPE
    && (['published', 'archived'].includes(row.status) ? typeof row.generated_at === 'string' && Number.isFinite(Date.parse(row.generated_at))
      : allowDraft && row.status === 'draft' && row.generated_at === null)
    && (row.coverage_percentage === null || typeof row.coverage_percentage === 'number' && Number.isFinite(row.coverage_percentage) && row.coverage_percentage >= 0 && row.coverage_percentage <= 100);
}
export function validateReports(data, page, allowDraft = false) {
  if (!Array.isArray(data?.results) || data.results.length > 9 || !Number.isSafeInteger(data.count) || data.count < data.results.length
    || data.page !== page || typeof data.has_next !== 'boolean' || data.has_next !== (page * 9 < data.count)
    || new Set(data.results.map(row => row?.report_id)).size !== data.results.length || !data.results.every(row => metadata(row, allowDraft))) throw new Error('The report list is incomplete. Please retry.');
  return data;
}
export async function loadReports(query, page, options = {}) {
  if (typeof query !== 'string' || query.length > 150 || !Number.isInteger(page) || page < 1 || page > 10000) throw new Error('Invalid report search.');
  const params = new URLSearchParams({ q: query, page: String(page) });
  return validateReports(await reportJSON(`/api/public/reports/?${params}`, options), page);
}
export function validateReport(data, id) {
  if (!metadata(data) || data.report_id !== id) throw new Error('The report is incomplete. Please retry.');
  const s = data.snapshot;
  if (s?.version !== 1 || s.radius_m !== 1000 || s.coverage_basis !== 'land_area_within_park_buffers' || s.report_type !== REPORT_TYPE
    || s.title !== 'Accessibility Coverage Report' || s.area_name !== data.area_name || s.reporting_period !== data.reporting_period
    || s.generated_at !== data.generated_at || !Array.isArray(s.sections) || !s.sections.length
    || new Set(s.sections).size !== s.sections.length || !s.sections.every(key => REPORT_SECTIONS.some(([name]) => name === key))
    || !Array.isArray(s.areas) || !Array.isArray(s.categories) || !Array.isArray(s.inventory) || s.inventory.length > 1000
    || typeof s.inventory_limited !== 'boolean' || !Array.isArray(s.limitations) || !s.limitations.every(v => typeof v === 'string')) throw new Error('The report snapshot is incomplete.');
  // Reuse the established measurement validation without treating a snapshot as live data.
  validateDashboard({ filters: { area: null, category: null }, radius_m: s.radius_m, coverage_basis: s.coverage_basis,
    options: { areas: s.areas, categories: s.categories }, areas: s.areas, categories: s.categories,
    summary: s.summary, priority_areas: [], priority_status: 'unavailable' });
  if (data.coverage_percentage !== s.summary.coverage_percentage || s.inventory_limited !== (s.summary.space_count > s.inventory.length)
    || s.inventory.length !== Math.min(1000, s.summary.space_count) || !s.inventory.every(r => Number.isSafeInteger(r.green_space_id)
      && typeof r.name === 'string' && typeof r.category_name === 'string' && ['POINT', 'POLYGON', 'MULTIPOLYGON'].includes(r.geometry_type)
      && (r.recorded_area_ha === null || typeof r.recorded_area_ha === 'string' && /^\d+(\.\d+)?$/.test(r.recorded_area_ha)))
    || new Set(s.inventory.map(r => r.green_space_id)).size !== s.inventory.length) throw new Error('The report inventory is inconsistent.');
  return data;
}
export async function loadReport(id, options = {}) {
  if (!Number.isSafeInteger(id) || id < 1) throw new Error('Invalid report.');
  return validateReport(await reportJSON(`/api/public/reports/${id}/`, options), id);
}
export function reportDate(value) { return value ? new Date(value).toLocaleDateString('en-MY', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kuala_Lumpur' }) : 'Not published'; }
