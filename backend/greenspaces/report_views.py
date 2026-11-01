"""FR7/FR11. Drafts are private; published snapshots never query live metrics."""
import logging
from functools import wraps
from django.core.exceptions import RequestDataTooBig
from django.core.paginator import EmptyPage, Paginator
from django.db import DatabaseError, IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from config.api import error, staff_permission
from .dashboard_views import DashboardUnavailable, dashboard_data
from .map_queries import positive_integer
from .models import AdministrativeArea, PlanningReport
from .nearby_views import payload, study_area
from .report_contract import REPORT_TYPE, SECTIONS, build_snapshot, parse_report

logger = logging.getLogger(__name__)


def report_response(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            response = view(request, *args, **kwargs)
        except (ValueError, UnicodeDecodeError):
            response = error('Check the report configuration or search values.', 400)
        except RequestDataTooBig:
            response = error('The report request is too large.', 413)
        except DashboardUnavailable as exc:
            response = error(str(exc), 503, code=exc.code)
        except IntegrityError:
            response = error('This request is already being saved. Retry with the same request key.', 409)
        except DatabaseError:
            logger.warning('Planning report database unavailable')
            response = error('Report data is unavailable. Please retry.', 503)
        response['Cache-Control'] = 'no-store'
        return response
    return wrapped


def summary(record):
    snapshot = record.snapshot or {}
    return {'report_id': record.pk, 'title': record.title, 'report_type': record.report_type,
            'reporting_period': record.reporting_period, 'area_name': snapshot.get('area_name') or (record.area.area_name if record.area else 'Petaling District'),
            'status': record.status, 'generated_at': record.generated_at.isoformat() if record.generated_at else None,
            'coverage_percentage': snapshot.get('summary', {}).get('coverage_percentage')}


def report_list(request, records):
    params = request.GET
    if set(params) - {'q', 'page'} or any(len(params.getlist(k)) != 1 for k in params):
        raise ValueError()
    query = params.get('q', '').strip()
    if len(query) > 150:
        raise ValueError()
    page_number = positive_integer(params.get('page', '1'), 'page', maximum=10000)
    if query:
        records = records.filter(title__icontains=query)
    paginator = Paginator(records.select_related('area').order_by('-report_id'), 9)
    try:
        page = paginator.page(page_number)
        results, more = [summary(r) for r in page.object_list], page.has_next()
    except EmptyPage:
        results, more = [], False
    return JsonResponse({'results': results, 'count': paginator.count, 'page': page_number, 'has_next': more})


def public_records():
    return PlanningReport.objects.filter(status__in=('published', 'archived'), generated_at__isnull=False, snapshot__isnull=False).exclude(snapshot={})


@require_GET
@report_response
def published(request):
    return report_list(request, public_records())


@require_GET
@report_response
def published_detail(request, report_id):
    record = public_records().select_related('area').filter(pk=report_id).first()
    if record is None:
        return error('No report available', 404)
    return JsonResponse({**summary(record), 'snapshot': record.snapshot})


@require_GET
@staff_permission('greenspaces.view_planningreport')
@report_response
def options(request):
    district = study_area()
    if district is None:
        raise DashboardUnavailable('Configure the Petaling district boundary first.', 'study_area_unavailable')
    areas = AdministrativeArea.objects.filter(geometry__intersects=district.geometry)
    return JsonResponse({'csrf_token': get_token(request), 'report_types': [REPORT_TYPE], 'sections': list(SECTIONS),
        'areas': list(areas.values('area_id', 'area_name', 'area_type')),
        'can_create': request.user.has_perm('greenspaces.add_planningreport')})


@require_GET
@staff_permission('greenspaces.view_planningreport')
@report_response
def drafts(request):
    # Each administrator's draft configuration remains private to that account.
    return report_list(request, PlanningReport.objects.filter(administrator=request.user, status='draft'))


@require_GET
@staff_permission('greenspaces.view_planningreport')
@report_response
def draft_detail(request, report_id):
    record = PlanningReport.objects.select_related('area').filter(pk=report_id, administrator=request.user, status='draft').first()
    if record is None:
        return error('This draft is unavailable.', 404)
    return JsonResponse({**summary(record), 'configuration': record.configuration})


def save_report(request, publish):
    config, key = parse_report(payload(request))
    with transaction.atomic():
        existing = PlanningReport.objects.filter(request_key=key).first()
        if existing:
            if existing.administrator_id != request.user.pk or existing.configuration != config or existing.status != ('published' if publish else 'draft'):
                return error('The request key belongs to another saved configuration.', 409)
            return JsonResponse({**summary(existing), 'snapshot': existing.snapshot, 'configuration': existing.configuration}, status=200)
        if config['area'] is not None and not AdministrativeArea.objects.filter(pk=config['area']).exists():
            raise ValueError('Unknown area')
        # A draft needs no available park dataset. Publishing requires computed data.
        generated_at, snapshot = None, None
        if publish:
            data = dashboard_data({'area': config['area'], 'category': None}, include_inventory=True)
            generated_at = timezone.now()
            snapshot = build_snapshot(data, config, generated_at.isoformat(), data['inventory'])
        record = PlanningReport.objects.create(administrator=request.user, area_id=config['area'],
            title=f"{REPORT_TYPE} — {config['reporting_period']}", report_type=REPORT_TYPE,
            reporting_period=config['reporting_period'], status='published' if publish else 'draft',
            generated_at=generated_at, configuration=config, snapshot=snapshot, request_key=key)
    return JsonResponse({**summary(record), 'snapshot': snapshot, 'configuration': config}, status=201)


@require_POST
@staff_permission('greenspaces.view_planningreport')
@staff_permission('greenspaces.add_planningreport')
@report_response
def generate(request):
    return save_report(request, publish=True)


@require_POST
@staff_permission('greenspaces.view_planningreport')
@staff_permission('greenspaces.add_planningreport')
@report_response
def save_draft(request):
    return save_report(request, publish=False)
