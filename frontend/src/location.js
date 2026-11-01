import district from '../../data/petaling-district.json' with { type: 'json' };

export const DEFAULT_RADIUS = 1000;
export function validCoordinates(point) {
  return point && typeof point.latitude === 'number' && typeof point.longitude === 'number'
    && Number.isFinite(point.latitude) && Number.isFinite(point.longitude)
    && Math.abs(point.latitude) <= 90 && Math.abs(point.longitude) <= 180;
}
export function parseCoordinates(text) {
  const parts = text.split(',').map(part => part.trim());
  if (parts.length !== 2 || !parts.every(part => /^[+-]?\d+(?:\.\d+)?$/.test(part))) return null;
  const point = { latitude: Number(parts[0]), longitude: Number(parts[1]) };
  return validCoordinates(point) ? { ...point, label: `${point.latitude.toFixed(6)}, ${point.longitude.toFixed(6)}` } : null;
}
export function coordinateLabel(point) {
  return validCoordinates(point) ? `${point.latitude.toFixed(6)}° N, ${point.longitude.toFixed(6)}° E` : '';
}
function inRing(x, y, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [ax, ay] = ring[j], [bx, by] = ring[i];
    const cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax);
    if (Math.abs(cross) < 1e-12 && x >= Math.min(ax, bx) && x <= Math.max(ax, bx)
      && y >= Math.min(ay, by) && y <= Math.max(ay, by)) return 0;
    if ((by > y) !== (ay > y) && x < (ax - bx) * (y - by) / (ay - by) + bx) inside = !inside;
  }
  return inside ? 1 : -1;
}
export function withinDistrict(point, collection = district) {
  if (!validCoordinates(point)) return false;
  const { longitude: x, latitude: y } = point;
  return collection.features.some(({ geometry }) => {
    const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
    return polygons.some(([outer, ...holes]) => inRing(x, y, outer) >= 0 && !holes.some(hole => inRing(x, y, hole) === 1));
  });
}
export function validRadius(value) {
  return ['string', 'number'].includes(typeof value) && String(value).trim() !== '' && Number.isInteger(Number(value))
    && Number(value) >= 100 && Number(value) <= 10000;
}
export function formatDistance(value) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return 'Not provided';
  return value < 1000 ? `${Math.round(value)} m` : `${(value / 1000).toLocaleString('en-MY', { maximumFractionDigits: 2 })} km`;
}
export function currentLocation({ geolocation = navigator.geolocation, secure = window.isSecureContext } = {}) {
  return new Promise((resolve, reject) => {
    if (!secure || !geolocation) { reject(new Error('Current location is unavailable. Use HTTPS or select a point on the map.')); return; }
    geolocation.getCurrentPosition(position => {
      const point = { latitude: position.coords.latitude, longitude: position.coords.longitude,
        accuracy_m: position.coords.accuracy, label: 'Current location' };
      if (!validCoordinates(point)) reject(new Error('The device did not return a valid location. Select a point on the map.'));
      else resolve(point);
    }, error => reject(new Error(error.code === 1 ? 'Location permission was denied. Allow it in your browser or select a point on the map.'
      : error.code === 3 ? 'Finding your location took too long. Try again or select a point on the map.'
        : 'Your current location could not be identified. Select a point on the map.')),
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
  });
}
