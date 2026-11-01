import math
from unittest.mock import patch
from django.contrib.gis.geos import Point, Polygon
from django.db import DatabaseError
from django.test import Client, TestCase
from django.urls import reverse
from .models import AdministrativeArea, GreenSpace, GreenSpaceCategory


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.district = AdministrativeArea.objects.create(area_name='Petaling', area_type='District',
            geometry=Polygon(((101.4,3),(101.8,3),(101.8,3.3),(101.4,3.3),(101.4,3)), srid=4326))
        cls.west = AdministrativeArea.objects.create(area_name='TEST West', area_type='Test zone',
            geometry=Polygon(((101.4,3),(101.6,3),(101.6,3.3),(101.4,3.3),(101.4,3)), srid=4326))
        cls.outside = AdministrativeArea.objects.create(area_name='TEST Outside', area_type='Test zone',
            geometry=Polygon(((102,3),(102.1,3),(102.1,3.1),(102,3.1),(102,3)), srid=4326))
        cls.public = GreenSpaceCategory.objects.create(category_name='TEST Public park')
        cls.garden = GreenSpaceCategory.objects.create(category_name='TEST Garden')
        cls.empty_category = GreenSpaceCategory.objects.create(category_name='TEST Empty category')
        cls.point = cls.park('TEST Point', Point(101.6005,3.1,srid=4326), cls.garden)
        cls.polygon = cls.park('TEST Polygon', Polygon(((101.579,3.099),(101.581,3.099),
            (101.581,3.101),(101.579,3.101),(101.579,3.099)), srid=4326), cls.public)

    @classmethod
    def park(cls, name, geom, category):
        return GreenSpace.objects.create(name=name, geometry=geom, category=category, area=cls.district)

    def dashboard(self, **filters):
        return self.client.get(reverse('public-dashboard'), filters)

    def test_anonymous_summary_categories_and_no_private_metadata(self):
        response = self.dashboard(); self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['summary']['space_count'], 2)
        self.assertEqual(sum(c['space_count'] for c in data['categories']), 2)
        self.assertEqual(data['summary']['area_status'], 'partial')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertNotIn('dataset_id', response.content.decode())

    def test_overlapping_parks_do_not_double_count_land_or_footprint(self):
        before = self.dashboard().json()['summary']
        self.park('TEST Duplicate polygon', self.polygon.geometry, self.public)
        after = self.dashboard().json()['summary']
        self.assertEqual(after['space_count'], 3)
        for key in ('green_area_ha', 'covered_land_ha'):
            self.assertAlmostEqual(before[key], after[key], places=6)

    def test_category_filter_point_only_uses_metres_not_degrees(self):
        data = self.dashboard(category=self.garden.pk).json()
        self.assertEqual(data['summary']['space_count'], 1)
        self.assertIsNone(data['summary']['green_area_ha'])
        self.assertAlmostEqual(data['summary']['covered_land_ha'], math.pi * 100, delta=2)
        self.assertEqual([c['category_id'] for c in data['categories']], [self.garden.pk])

    def test_area_filter_is_spatial_not_foreign_key_membership(self):
        data = self.dashboard(area=self.west.pk).json()
        self.assertEqual(data['summary']['space_count'], 1)
        self.assertEqual([a['area_id'] for a in data['areas']], [self.west.pk])
        self.assertEqual(data['summary']['area_status'], 'complete')

    def test_neighbour_park_can_cover_land_without_being_counted_in_area(self):
        data = self.dashboard(area=self.west.pk, category=self.garden.pk).json()
        self.assertEqual(data['summary']['space_count'], 0)
        self.assertGreater(data['summary']['covered_land_ha'], 100)
        self.assertLess(data['summary']['covered_land_ha'], 170)

    def test_empty_category_is_valid_zero_not_missing_dataset(self):
        response = self.dashboard(category=self.empty_category.pk)
        self.assertEqual(response.status_code, 200)
        metrics = response.json()['summary']
        self.assertEqual((metrics['space_count'], metrics['green_area_ha'], metrics['coverage_percentage']), (0,0,0))

    def test_outside_or_unknown_areas_and_categories_are_invalid(self):
        for filters in ({'area': self.outside.pk}, {'area': 999999}, {'category': 999999}):
            self.assertEqual(self.dashboard(**filters).status_code, 400)
        ids = [a['area_id'] for a in self.dashboard().json()['options']['areas']]
        self.assertNotIn(self.outside.pk, ids)

    def test_invalid_duplicate_and_unsupported_parameters(self):
        for query in ('area=1&area=2', 'area=', 'category=-1', 'radius_m=500', 'area=1.5'):
            self.assertEqual(self.client.get(reverse('public-dashboard') + '?' + query).status_code, 400)

    def test_missing_park_data_and_missing_or_ambiguous_district_fail(self):
        with patch('greenspaces.dashboard_views.study_area', return_value=None):
            self.assertEqual(self.dashboard().status_code, 503)
        GreenSpace.objects.all().delete()
        self.assertEqual(self.dashboard().status_code, 503)

    def test_database_error_hides_sql_and_has_no_store(self):
        with patch('greenspaces.dashboard_views.study_area', side_effect=DatabaseError('private SQL details')):
            response = self.dashboard()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private SQL', response.content.decode())
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_no_fabricated_population_priority_or_historical_change(self):
        data = self.dashboard().json()
        for key in ('planning_gaps', 'population_gap', 'population_covered', 'baseline_change_percentage'):
            self.assertIsNone(data['summary'][key])
        self.assertEqual(data['priority_areas'], [])
        self.assertEqual(data['coverage_basis'], 'land_area_within_park_buffers')

    def test_read_only_public_access_and_wrong_methods(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get(reverse('public-dashboard')).status_code, 200)
        self.assertEqual(GreenSpace.objects.count(), 2)
        for method in (self.client.post, self.client.put, self.client.delete):
            self.assertEqual(method(reverse('public-dashboard')).status_code, 405)
