import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { CATEGORIES, MAP_ERROR, categoryRows } from '../src/prototype.js';

test('prototype category wording and order are preserved without fake counts', () => {
  const rows = categoryRows([]);
  assert.deepEqual(rows.map(row => row.category_name), CATEGORIES);
  assert.ok(rows.every(row => row.green_space_count === null && row.category_id === null));
});
test('real counts including zero are retained and input is not mutated', () => {
  const input = [{ category_id: 9, category_name: 'Community garden', green_space_count: 0 },
    { category_id: 20, category_name: 'Uploaded extra category', green_space_count: 2 }];
  const rows = categoryRows(input);
  assert.equal(rows[3].green_space_count, 0);
  assert.equal(rows[3].category_id, 9);
  assert.equal(rows[4].category_name, 'Uploaded extra category');
  assert.equal(input.length, 2);
});
test('map error uses the reference wording', () => {
  assert.deepEqual(MAP_ERROR, { title: 'Map could not be loaded', subtitle: 'Unable to display the interactive map.',
    message: 'There was a problem loading the map.', guidance: 'Please check the connection and try again.' });
});
test('seed contains only a sourced Petaling boundary and closed WGS84 rings', () => {
  const seed = JSON.parse(readFileSync(new URL('../../data/petaling-district.json', import.meta.url)));
  assert.equal(seed.features.length, 1);
  assert.match(seed.source.url, /dosm-malaysia\/data-open\/blob\/21a78e98/);
  const feature = seed.features[0];
  assert.equal(feature.properties.district, 'Petaling');
  assert.equal(feature.properties.state, 'Selangor');
  assert.equal(feature.geometry.type, 'MultiPolygon');
  for (const polygon of feature.geometry.coordinates) for (const ring of polygon) {
    assert.ok(ring.length >= 4);
    assert.deepEqual(ring[0], ring.at(-1));
    assert.ok(ring.every(([lon, lat]) => lon > 101 && lon < 102 && lat > 2.9 && lat < 3.3));
  }
});
