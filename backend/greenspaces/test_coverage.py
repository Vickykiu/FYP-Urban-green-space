import math
from unittest.mock import patch

from django.contrib.gis.geos import GEOSGeometry, Point, Polygon
from django.db import DatabaseError, connection
from django.test import Client, TestCase
from django.urls import reverse

from .models import AdministrativeArea, GreenSpace, GreenSpaceCategory


class CoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.area = AdministrativeArea.objects.create(area_name='Petaling', area_type='District',
            geometry=Polygon(((101.4,3),(101.8,3),(101.8,3.3),(101.4,3.3),(101.4,3)), srid=4326))
        cls.category = GreenSpaceCategory.objects.create(category_name='Public park')
        cls.point = cls.park('TEST Point', Point(101.6, 3.1, srid=4326))
        cls.polygon = cls.park('TEST Polygon', Polygon(((101.599,3.099),(101.601,3.099),
            (101.601,3.101),(101.599,3.101),(101.599,3.099)), srid=4326))

    @classmethod
    def park(cls, name, geometry):
        return GreenSpace.objects.create(name=name, geometry=geometry, area=cls.area, category=cls.category)

    def analyse(self, **changes):
        return self.client.post(reverse('public-accessibility'), {
            'latitude': 3.1, 'longitude': 101.6, 'radius_m': 1000, **changes}, content_type='application/json')

    def test_anonymous_coverage_uses_metres_and_nullable_population(self):
        response = self.analyse(); self.assertEqual(response.status_code, 200)
        data = response.json(); metrics = data['metrics']
        self.assertEqual(metrics['green_spaces_reached'], 2)
        self.assertIsNone(metrics['population_covered'])
        self.assertAlmostEqual(metrics['coverage_area_ha'], math.pi * 100, delta=2)
        self.assertGreater(metrics['total_accessible_area_ha'], 4)
        self.assertLess(metrics['total_accessible_area_ha'], 6)
        self.assertEqual(metrics['area_status'], 'partial')
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_overlapping_polygon_records_are_not_double_counted_in_area(self):
        before = self.analyse().json()['metrics']
        self.park('TEST Duplicate footprint', self.polygon.geometry)
        after = self.analyse().json()['metrics']
        self.assertEqual(after['green_spaces_reached'], before['green_spaces_reached'] + 1)
        self.assertAlmostEqual(after['total_accessible_area_ha'], before['total_accessible_area_ha'], places=6)

    def test_point_only_park_has_no_invented_footprint(self):
        self.polygon.delete()
        data = self.analyse().json()['metrics']
        self.assertIsNone(data['total_accessible_area_ha'])
        self.assertEqual(data['area_status'], 'unavailable')

    def test_empty_search_is_zero_but_missing_dataset_is_failure(self):
        empty = self.analyse(latitude=3.2).json()['metrics']
        self.assertEqual((empty['green_spaces_reached'], empty['total_accessible_area_ha']), (0, 0))
        GreenSpace.objects.all().delete()
        response = self.analyse()
        self.assertEqual((response.status_code, response.json()['code']), (503, 'green_space_data_unavailable'))

    def test_custom_band_is_added_without_losing_comparison_bands(self):
        data = self.analyse(radius_m=750).json()
        self.assertEqual([f['properties']['radius_m'] for f in data['coverage']['features']], [500,750,1000,2000])
        self.assertEqual(sum(f['properties']['selected'] for f in data['coverage']['features']), 1)

    def test_district_clips_coverage_without_changing_distance_units(self):
        full = self.analyse().json()['metrics']['coverage_area_ha']
        self.area.geometry = Polygon(((101.6,3),(101.8,3),(101.8,3.3),(101.6,3.3),(101.6,3)), srid=4326)
        self.area.save(update_fields=['geometry'])
        data = self.analyse().json()
        self.assertAlmostEqual(data['metrics']['coverage_area_ha'], full / 2, delta=2)
        for band in data['coverage']['features']:
            self.assertGreaterEqual(min(p[0] for p in band['geometry']['coordinates'][0]), 101.6 - 1e-8)

    def test_exact_distance_edge_and_baseline_delta(self):
        for name, distance in [('TEST inside', 999.99), ('TEST outside', 1000.01)]:
            with connection.cursor() as cursor:
                cursor.execute('SELECT ST_AsEWKT(ST_Project(%s::geography, %s, 0)::geometry)',
                               ['SRID=4326;POINT(101.6 3.1)', distance])
                self.park(name, GEOSGeometry(cursor.fetchone()[0]))
        data = self.analyse().json()
        self.assertEqual(data['metrics']['change_from_500_m'], 1)
        names = [f['properties']['name'] for f in data['green_spaces']['features']]
        self.assertIn('TEST inside', names); self.assertNotIn('TEST outside', names)

    def test_count_includes_records_beyond_display_limit(self):
        with patch('greenspaces.coverage_views.DISPLAY_LIMIT', 1):
            data = self.analyse().json()
        self.assertEqual(data['metrics']['green_spaces_reached'], 2)
        self.assertEqual(len(data['green_spaces']['features']), 1)
        self.assertTrue(data['green_spaces']['limited'])

    def test_invalid_origin_radius_or_extra_fields(self):
        for changes in ({'latitude': 99}, {'longitude': 102}, {'radius_m': 99}, {'radius_m': True}, {'page': 1}):
            self.assertEqual(self.analyse(**changes).status_code, 400)

    def test_missing_district_and_database_error_are_not_empty_success(self):
        with patch('greenspaces.coverage_views.study_area', return_value=None):
            self.assertEqual(self.analyse().status_code, 503)
        with patch('greenspaces.coverage_views.study_area', side_effect=DatabaseError('private SQL')):
            response = self.analyse()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private SQL', response.content.decode())

    def test_csrf_protection_without_account_requirement_and_no_writes(self):
        client = Client(enforce_csrf_checks=True)
        body = {'latitude': 3.1, 'longitude': 101.6, 'radius_m': 1000}
        self.assertEqual(client.post(reverse('public-accessibility'), body, content_type='application/json').status_code, 403)
        token = client.get(reverse('public-nearby-options')).json()['csrf_token']
        self.assertEqual(client.post(reverse('public-accessibility'), body, content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertEqual(GreenSpace.objects.count(), 2)

    def test_only_post_is_allowed(self):
        for method in (self.client.get, self.client.put, self.client.delete):
            self.assertEqual(method(reverse('public-accessibility')).status_code, 405)
