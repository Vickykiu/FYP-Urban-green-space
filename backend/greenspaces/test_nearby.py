import json
from unittest.mock import patch

from django.contrib.gis.geos import GEOSGeometry, Point, Polygon
from django.db import DatabaseError, connection
from django.test import Client, TestCase
from django.urls import reverse

from .models import AdministrativeArea, GreenSpace, GreenSpaceCategory


class NearbyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.area = AdministrativeArea.objects.create(area_name='Petaling', area_type='District',
            geometry=Polygon(((101.4, 3), (101.8, 3), (101.8, 3.3), (101.4, 3.3), (101.4, 3)), srid=4326))
        cls.category = GreenSpaceCategory.objects.create(category_name='Public park')
        cls.near = cls.park('TEST Near park', Point(101.6, 3.104, srid=4326))
        cls.far = cls.park('TEST Further park', Point(101.6, 3.11, srid=4326))
        cls.polygon = cls.park('TEST Polygon park', Polygon(((101.59, 3.09), (101.61, 3.09),
            (101.61, 3.11), (101.59, 3.11), (101.59, 3.09)), srid=4326))

    @classmethod
    def park(cls, name, geometry):
        return GreenSpace.objects.create(name=name, area=cls.area, category=cls.category, geometry=geometry)

    def search(self, **values):
        return self.client.post(reverse('public-nearby'), json.dumps(
            {'latitude': 3.1, 'longitude': 101.6, 'radius_m': 500, **values}), content_type='application/json')

    def test_anonymous_nearby_sorted_in_metres(self):
        response = self.search()
        self.assertEqual(response.status_code, 200)
        features = response.json()['features']
        self.assertEqual([f['id'] for f in features], [self.polygon.pk, self.near.pk])
        self.assertEqual(features[0]['properties']['distance_m'], 0)
        self.assertGreater(features[1]['properties']['distance_m'], 400)
        self.assertLess(features[1]['properties']['distance_m'], 500)
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_larger_radius_adds_further_records(self):
        self.assertEqual(self.search(radius_m=2000).json()['count'], 3)

    def test_radius_edge_uses_actual_not_rounded_distance(self):
        for name, metres in [('TEST just inside', 999.99), ('TEST just outside', 1000.01)]:
            with connection.cursor() as cursor:
                cursor.execute('SELECT ST_AsEWKT(ST_Project(%s::geography, %s, 0)::geometry)',
                               ['SRID=4326;POINT(101.6 3.1)', metres])
                self.park(name, GEOSGeometry(cursor.fetchone()[0]))
        names = [f['properties']['name'] for f in self.search(radius_m=1000).json()['features']]
        self.assertIn('TEST just inside', names)
        self.assertNotIn('TEST just outside', names)

    def test_polygon_hole_is_not_zero_distance(self):
        outer = ((101.58, 3.08), (101.62, 3.08), (101.62, 3.12), (101.58, 3.12), (101.58, 3.08))
        hole = ((101.599, 3.099), (101.601, 3.099), (101.601, 3.101), (101.599, 3.101), (101.599, 3.099))
        park = self.park('TEST Ring', Polygon(outer, hole, srid=4326))
        feature = next(f for f in self.search().json()['features'] if f['id'] == park.pk)
        self.assertGreater(feature['properties']['distance_m'], 100)

    def test_invalid_or_outside_location_is_not_an_empty_success(self):
        for values in ({'latitude': 99}, {'longitude': 102}, {'radius_m': -1}, {'page': 1.5}):
            self.assertEqual(self.search(**values).status_code, 400)
        self.assertEqual(self.search(longitude=102).json()['code'], 'outside_study_area')

    def test_missing_study_area_is_an_explicit_configuration_error(self):
        self.area.area_type = 'test'
        self.area.save(update_fields=['area_type'])
        response = self.search()
        self.assertEqual((response.status_code, response.json()['code']), (503, 'study_area_unavailable'))

    def test_duplicate_keys_and_nonfinite_json_rejected(self):
        for body in ('{"latitude":3,"latitude":4,"longitude":101,"radius_m":500}',
                     '{"latitude":NaN,"longitude":101,"radius_m":500}', '[]'):
            self.assertEqual(self.client.post(reverse('public-nearby'), body, content_type='application/json').status_code, 400)

    def test_pagination_and_stable_distance_ties(self):
        twin = self.park('TEST Twin', self.near.geometry)
        with patch('greenspaces.nearby_views.PAGE_SIZE', 1):
            first, second, third = (self.search(page=n).json() for n in (1, 2, 3))
        self.assertTrue(first['has_next'])
        self.assertEqual(second['features'][0]['id'], self.near.pk)
        self.assertEqual(third['features'][0]['id'], twin.pk)
        self.assertFalse(third['has_next'])

    def test_place_search_uses_uploaded_names_and_point_on_surface(self):
        response = self.client.post(reverse('public-place-search'), {'q': 'Polygon'}, content_type='application/json')
        data = response.json()
        self.assertFalse(data['street_address_lookup'])
        self.assertEqual(data['results'][0]['id'], self.polygon.pk)
        result = data['results'][0]
        self.assertTrue(self.polygon.geometry.covers(Point(result['longitude'], result['latitude'], srid=4326)))

    def test_unmatched_address_is_not_fabricated(self):
        response = self.client.post(reverse('public-place-search'), {'q': 'unlisted street'}, content_type='application/json')
        self.assertEqual(response.json()['results'], [])

    def test_csrf_required_without_login_requirement(self):
        client = Client(enforce_csrf_checks=True)
        body = {'latitude': 3.1, 'longitude': 101.6, 'radius_m': 500}
        self.assertEqual(client.post(reverse('public-nearby'), body, content_type='application/json').status_code, 403)
        token = client.get(reverse('public-nearby-options')).json()['csrf_token']
        self.assertEqual(client.post(reverse('public-nearby'), body, content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_routes_reject_wrong_methods_and_do_not_write_records(self):
        for name in ('public-nearby', 'public-place-search'):
            for method in (self.client.get, self.client.put, self.client.delete):
                self.assertEqual(method(reverse(name)).status_code, 405)
        self.search()
        self.assertEqual(GreenSpace.objects.count(), 3)

    def test_unavailable_database_does_not_leak_details(self):
        with patch('greenspaces.nearby_views.study_area', side_effect=DatabaseError('private test details')):
            response = self.search()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private test details', response.content.decode())
