export async function getJSON(url, { signal, fetcher = fetch } = {}) {
  const response = await fetcher(url, { signal, headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(response.status === 404 ? 'This record is no longer available.'
    : 'Map data is unavailable. Check the backend connection and try again.');
  try { return await response.json(); }
  catch { throw new Error('The server did not return valid map data.'); }
}

export async function loadCollection(endpoint, params, options = {}) {
  const byId = new Map();
  let count = 0, hasNext = false;
  // Bound automatic work: 200 features/page, at most 2,000 per viewport.
  for (let page = 1; page <= 10; page += 1) {
    const query = new URLSearchParams({ ...params, page: String(page) });
    const data = await getJSON(`${endpoint}?${query}`, options);
    if (data.type !== 'FeatureCollection' || !Array.isArray(data.features)
      || !Number.isInteger(data.count) || data.count < 0 || typeof data.has_next !== 'boolean') {
      throw new Error('The server returned an unexpected map-data format.');
    }
    count = data.count;
    for (const feature of data.features) {
      if (feature.type !== 'Feature' || feature.id == null || !feature.geometry || !feature.properties) {
        throw new Error('A map record is incomplete. Please retry.');
      }
      byId.set(feature.id, feature);
      if (byId.size >= 2000) break;
    }
    hasNext = data.has_next;
    if (!hasNext || byId.size >= 2000) break;
  }
  return { features: [...byId.values()], count, limited: hasNext || count > byId.size };
}

export function formatArea(value) {
  if (value === null || value === undefined || value === '') return 'Not provided';
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toLocaleString('en-MY', { maximumFractionDigits: 4 })} ha` : 'Not provided';
}
