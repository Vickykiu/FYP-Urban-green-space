import { getJSON } from './mapApi.js';

export async function publicQuery(endpoint, payload, { signal, fetcher = fetch, csrfToken } = {}) {
  const token = csrfToken || (await getJSON('/api/public/nearby/options/', { signal, fetcher })).csrf_token;
  if (typeof token !== 'string' || !token) throw new Error('Search could not connect. Please try again.');
  const response = await fetcher(endpoint, { method: 'POST', signal, credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': token }, body: JSON.stringify(payload) });
  let data;
  try { data = await response.json(); } catch { throw new Error('Search data is unavailable. Please try again.'); }
  if (!response.ok) {
    const messages = {
      outside_study_area: 'Select a starting location inside Petaling District.',
      study_area_unavailable: 'The Petaling district data is not ready. Please try again after database setup.',
      invalid_query: 'Check the location and search radius, then try again.',
      green_space_data_unavailable: 'Green-space data is not ready. An administrator must import approved CSV records first.',
    };
    const error = new Error(messages[data.code] || 'Search data is unavailable. Please try again.');
    error.code = data.code;
    throw error;
  }
  return data;
}

export async function searchNearby(origin, radius, { signal, fetcher = fetch } = {}) {
  const { csrf_token: csrfToken } = await getJSON('/api/public/nearby/options/', { signal, fetcher });
  const features = new Map();
  let count = 0, hasNext = false;
  for (let page = 1; page <= 10; page += 1) {
    const data = await publicQuery('/api/public/nearby/', {
      latitude: origin.latitude, longitude: origin.longitude, radius_m: Number(radius), page,
    }, { signal, fetcher, csrfToken });
    if (data.type !== 'FeatureCollection' || !Array.isArray(data.features) || !Number.isInteger(data.count)
      || data.count < 0 || typeof data.has_next !== 'boolean' || data.radius_m !== Number(radius)
      || data.distance_method !== 'spheroidal_straight_line_to_geometry') throw new Error('The search returned an unexpected format.');
    count = data.count;
    for (const feature of data.features) {
      const distance = feature.properties?.distance_m;
      if (feature.type !== 'Feature' || !Number.isInteger(feature.id) || !feature.geometry || !feature.properties
        || typeof distance !== 'number' || !Number.isFinite(distance) || distance < 0 || distance > Number(radius) + 0.000001) {
        throw new Error('A nearby result is incomplete or outside the requested radius.');
      }
      features.set(feature.id, feature);
      if (features.size >= 2000) break;
    }
    hasNext = data.has_next;
    if (!hasNext || features.size >= 2000) break;
  }
  return { features: [...features.values()].sort((a, b) => a.properties.distance_m - b.properties.distance_m || a.id - b.id),
    count, limited: hasNext || count > features.size };
}
