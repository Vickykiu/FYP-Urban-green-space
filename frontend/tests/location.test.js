import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseCoordinates, validCoordinates, withinDistrict, validRadius, formatDistance, currentLocation } from '../src/location.js';

test('coordinate input uses explicit latitude then longitude', () => {
  const point = parseCoordinates('3.08, 101.60');
  assert.equal(point.latitude, 3.08); assert.equal(point.longitude, 101.6);
  for (const text of ['', 'Jalan Sentosa 12', '91,101', 'NaN,3', ',101', '1,2,3']) assert.equal(parseCoordinates(text), null);
  assert.equal(validCoordinates({ latitude: true, longitude: 101 }), false);
});
test('Petaling reference rejects a location outside the district', () => {
  assert.equal(withinDistrict({ latitude: 3.08, longitude: 101.6 }), true);
  assert.equal(withinDistrict({ latitude: 3.15, longitude: 101.7 }), false);
  assert.equal(withinDistrict({ latitude: 0, longitude: 0 }), false);
});
test('polygon holes are excluded but district edges are allowed', () => {
  const collection = { features: [{ geometry: { type: 'Polygon', coordinates: [
    [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]], [[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]],
  ] } }] };
  assert.equal(withinDistrict({ latitude: 1.5, longitude: 1.5 }, collection), false);
  assert.equal(withinDistrict({ latitude: 0, longitude: 2 }, collection), true);
  assert.equal(withinDistrict({ latitude: 3, longitude: 3 }, collection), true);
});
test('radius checks reject invalid numbers and types', () => {
  for (const value of [100, 500, '1000', 2000, 10000]) assert.equal(validRadius(value), true);
  for (const value of ['', null, true, [], [1000], 99, 10001, 500.5, 'NaN']) assert.equal(validRadius(value), false);
});
test('distance is labelled in metres or kilometres, never walking minutes', () => {
  assert.equal(formatDistance(0), '0 m'); assert.equal(formatDistance(600), '600 m');
  assert.equal(formatDistance(1500), '1.5 km'); assert.equal(formatDistance(null), 'Not provided');
});
test('current-location success requests location only when invoked', async () => {
  let calls = 0;
  const result = await currentLocation({ secure: true, geolocation: { getCurrentPosition(success, failure, options) {
    calls += 1; assert.equal(options.timeout, 10000);
    success({ coords: { latitude: 3.08, longitude: 101.6, accuracy: 25 } });
  } } });
  assert.equal(calls, 1); assert.equal(result.accuracy_m, 25);
});
test('permission denial, timeout, and unavailable location get useful errors', async () => {
  for (const [code, message] of [[1, /permission was denied/], [2, /could not be identified/], [3, /too long/]]) {
    await assert.rejects(currentLocation({ secure: true, geolocation: { getCurrentPosition(ok, fail) { fail({ code }); } } }), message);
  }
  await assert.rejects(currentLocation({ secure: false, geolocation: null }), /Use HTTPS/);
});
