import { publicQuery } from './nearbyApi.js';
import { validCoordinates, validRadius } from './location.js';

const nonnegative = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
function position(value) {
  return Array.isArray(value) && value.length >= 2 && validCoordinates({ longitude: value[0], latitude: value[1] });
}
function ring(value) {
  return Array.isArray(value) && value.length >= 4 && value.every(position)
    && value[0][0] === value.at(-1)[0] && value[0][1] === value.at(-1)[1];
}
function polygon(value) { return Array.isArray(value) && value.length > 0 && value.every(ring); }
function geometry(value, allowPoint = false) {
  return value && (value.type === 'Polygon' ? polygon(value.coordinates)
    : value.type === 'MultiPolygon' ? Array.isArray(value.coordinates) && value.coordinates.length > 0 && value.coordinates.every(polygon)
      : allowPoint && value.type === 'Point' && position(value.coordinates));
}
export function validateCoverage(data, radius) {
  const metrics = data?.metrics, bands = data?.coverage?.features, greens = data?.green_spaces;
  const invalid = () => { throw new Error('The analysis returned incomplete or inconsistent results. Please retry.'); };
  if (data?.method !== 'distance_buffer' || data.radius_m !== Number(radius)
    || data.coverage?.type !== 'FeatureCollection' || !Array.isArray(bands) || bands.length < 3 || bands.length > 4
    || !metrics || !greens || greens.type !== 'FeatureCollection' || !Array.isArray(greens.features) || greens.features.length > 2000) invalid();
  const expected = [...new Set([500, 1000, 2000, Number(radius)])].sort((a, b) => a - b);
  const actual = bands.map(f => f?.properties?.radius_m).sort((a, b) => a - b);
  if (JSON.stringify(actual) !== JSON.stringify(expected) || !bands.every(f => f.type === 'Feature' && geometry(f.geometry)
    && f.properties.selected === (f.properties.radius_m === Number(radius)) && nonnegative(f.properties.coverage_area_m2))) invalid();
  if (!Number.isInteger(metrics.green_spaces_reached) || metrics.green_spaces_reached < 0
    || !Number.isInteger(metrics.change_from_500_m) || !nonnegative(metrics.coverage_area_ha)
    || !Number.isInteger(metrics.point_records_without_footprint) || metrics.point_records_without_footprint < 0
    || metrics.point_records_without_footprint > metrics.green_spaces_reached
    || !['complete', 'partial', 'unavailable'].includes(metrics.area_status)
    || metrics.population_status !== 'unavailable' || metrics.population_covered !== null || metrics.population_percentage !== null) invalid();
  const area = metrics.total_accessible_area_ha, percent = metrics.accessible_area_percentage;
  if (metrics.area_status === 'unavailable' ? area !== null || percent !== null
    : !nonnegative(area) || area > metrics.coverage_area_ha + 0.000001 || !nonnegative(percent) || percent > 100) invalid();
  if (greens.count !== metrics.green_spaces_reached || typeof greens.limited !== 'boolean'
    || greens.features.length > greens.count || greens.limited !== (greens.count > greens.features.length)
    || new Set(greens.features.map(f => f?.id)).size !== greens.features.length
    || !greens.features.every(f => f?.type === 'Feature' && Number.isInteger(f.id) && geometry(f.geometry, true)
      && typeof f.properties?.name === 'string' && nonnegative(f.properties.distance_m) && f.properties.distance_m <= Number(radius) + 0.000001)) invalid();
  return data;
}
export async function analyseCoverage(origin, radius, options = {}) {
  if (!validCoordinates(origin) || !validRadius(radius)) throw new Error('Select a valid location and a distance from 100 to 10,000 m.');
  const data = await publicQuery('/api/public/accessibility/', {
    latitude: origin.latitude, longitude: origin.longitude, radius_m: Number(radius),
  }, options);
  return validateCoverage(data, radius);
}
export function formatCoverageArea(value) {
  return value == null ? 'Unavailable' : `${value.toLocaleString('en-MY', { maximumFractionDigits: 2 })} ha`;
}
export const ANALYSIS_ERROR = {
  title: 'Analysis failed', subtitle: 'The accessibility analysis could not be completed.',
  message: 'The selected location or required spatial data is unavailable.',
  guidance: 'Please select another location and try again.',
};
