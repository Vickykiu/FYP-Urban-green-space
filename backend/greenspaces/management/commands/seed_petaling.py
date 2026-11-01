"""Apply after schema migrations. Seeds reference data, never park records."""
import json
from pathlib import Path

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from greenspaces.models import AdministrativeArea, GreenSpaceCategory

CATEGORIES = ('Public park', 'Recreation field', 'Neighbourhood green', 'Community garden')


class Command(BaseCommand):
    help = 'Seed the DOSM Petaling district boundary and prototype categories; preserve existing records.'

    @transaction.atomic
    def handle(self, *args, **options):
        source = Path(settings.BASE_DIR).parent / 'data' / 'petaling-district.json'
        data = json.loads(source.read_text(encoding='utf-8'))
        if len(data['features']) != 1:
            raise CommandError('Expected exactly one Petaling boundary.')
        feature = data['features'][0]
        if feature['properties']['state'] != 'Selangor' or feature['properties']['district'] != 'Petaling':
            raise CommandError('The seed is not the Petaling district in Selangor.')
        geometry = GEOSGeometry(json.dumps(feature['geometry']), srid=4326)
        draft = AdministrativeArea(area_name='Petaling', area_type='District', geometry=geometry)
        draft.full_clean()
        # Serialize concurrent seed runs without imposing IDs or changing the ERD.
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [732086504])
        areas = AdministrativeArea.objects.filter(area_name='Petaling', area_type='District')
        if areas.count() > 1:
            raise CommandError('Multiple Petaling district records exist; review them before seeding.')
        area = areas.first()
        if area is None:
            draft.save()
            area = draft
            self.stdout.write(f'Created Petaling boundary: area_id={area.pk}')
        else:
            self.stdout.write(f'Kept existing Petaling boundary unchanged: area_id={area.pk}')
        for name in CATEGORIES:
            matches = GreenSpaceCategory.objects.filter(category_name=name)
            if matches.count() > 1:
                raise CommandError(f'Multiple categories named {name!r}; review them before seeding.')
            category = matches.first()
            if category is None:
                category = GreenSpaceCategory(category_name=name)
                category.full_clean()
                category.save()
            self.stdout.write(f'{name}: category_id={category.pk}')
        self.stdout.write(self.style.SUCCESS('Reference seed ready. No green-space records or accounts were added.'))
