"""Run with a disposable PostGIS test database once native GIS is installed."""
from io import StringIO

from django.contrib.gis.geos import Polygon
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import AdministrativeArea, GreenSpace, GreenSpaceCategory


class PetalingSeedTests(TestCase):
    def seed(self):
        call_command('seed_petaling', stdout=StringIO())

    def test_repeatable_reference_seed_without_parks(self):
        self.seed()
        area_id = AdministrativeArea.objects.get().pk
        category_ids = list(GreenSpaceCategory.objects.values_list('pk', flat=True))
        self.seed()
        self.assertEqual(AdministrativeArea.objects.get().pk, area_id)
        self.assertEqual(list(GreenSpaceCategory.objects.values_list('pk', flat=True)), category_ids)
        self.assertEqual(GreenSpaceCategory.objects.count(), 4)
        self.assertEqual(GreenSpace.objects.count(), 0)
        self.assertTrue(AdministrativeArea.objects.get().geometry.valid)

    def test_existing_boundary_is_not_overwritten(self):
        geometry = Polygon(((101.5, 3), (101.6, 3), (101.6, 3.1), (101.5, 3.1), (101.5, 3)), srid=4326)
        area = AdministrativeArea.objects.create(area_name='Petaling', area_type='District', geometry=geometry)
        self.seed()
        area.refresh_from_db()
        self.assertTrue(area.geometry.equals_exact(geometry))

    def test_ambiguous_category_rolls_back_boundary_creation(self):
        GreenSpaceCategory.objects.create(category_name='Public park')
        GreenSpaceCategory.objects.create(category_name='Public park')
        with self.assertRaises(CommandError):
            self.seed()
        self.assertEqual(AdministrativeArea.objects.count(), 0)
        self.assertEqual(GreenSpaceCategory.objects.count(), 2)
