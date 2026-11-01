import json

from django.core.paginator import EmptyPage, Paginator
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_GET, require_http_methods

from config.api import error, read_record_json, staff_permission
from .forms import GreenSpaceForm
from .models import AdministrativeArea, GreenSpace, GreenSpaceCategory


def serialize_record(record):
    return {
        "green_space_id": record.pk, "name": record.name,
        "area": record.area_id, "area_name": record.area.area_name,
        "category": record.category_id, "category_name": record.category.category_name,
        "dataset": record.dataset_id,
        "area_size": str(record.area_size) if record.area_size is not None else None,
        "facilities": record.facilities, "description": record.description,
        "latitude": str(record.latitude) if record.latitude is not None else None,
        "longitude": str(record.longitude) if record.longitude is not None else None,
        "geometry": json.loads(record.geometry.geojson),
    }


@require_GET
@staff_permission("greenspaces.view_greenspace")
def session(request):
    return JsonResponse({
        "username": request.user.username, "csrf_token": get_token(request),
        "permissions": {action: request.user.has_perm(f"greenspaces.{action}_greenspace")
                        for action in ("view", "add", "change", "delete")},
        "dataset_permissions": {
            "view": request.user.has_perm("greenspaces.view_datasetupload"),
            "upload": request.user.has_perm("greenspaces.add_datasetupload"),
            "validate": request.user.has_perm("greenspaces.change_datasetupload"),
            "import": (request.user.has_perm("greenspaces.change_datasetupload")
                       and request.user.has_perm("greenspaces.add_greenspace")),
        },
    })


@require_GET
@staff_permission("greenspaces.view_greenspace")
def lookups(request):
    return JsonResponse({
        "areas": list(AdministrativeArea.objects.values("area_id", "area_name")),
        "categories": list(GreenSpaceCategory.objects.values("category_id", "category_name")),
    })


@staff_permission("greenspaces.view_greenspace")
def list_records(request):
    try:
        page_number = int(request.GET.get("page", "1"))
        if page_number < 1:
            raise ValueError
    except ValueError:
        return error("page must be a positive integer.", 400)
    records = GreenSpace.objects.select_related("area", "category").all()
    query = request.GET.get("q", "").strip()
    if len(query) > 150:
        return error("Search text must not exceed 150 characters.", 400)
    if query:
        records = records.filter(name__icontains=query)
    paginator = Paginator(records, 50)
    try:
        page = paginator.page(page_number)
        result = [serialize_record(record) for record in page.object_list]
        has_next = page.has_next()
    except EmptyPage:
        result, has_next = [], False
    return JsonResponse({"count": paginator.count, "page": page_number,
                         "page_size": 50, "has_next": has_next, "results": result})


@staff_permission("greenspaces.add_greenspace")
def create_record(request):
    payload, failure = read_record_json(request, GreenSpaceForm.Meta.fields)
    if failure is not None:
        return failure
    with transaction.atomic():
        form = GreenSpaceForm(payload)
        if not form.is_valid():
            return error("Correct the invalid record fields.", 400, fields=form.errors.get_json_data())
        record = form.save()
        return JsonResponse(serialize_record(record), status=201)


@require_http_methods(["GET", "POST"])
def records(request):
    return list_records(request) if request.method == "GET" else create_record(request)


@staff_permission("greenspaces.view_greenspace")
def retrieve_record(request, record_id):
    record = GreenSpace.objects.select_related("area", "category").filter(pk=record_id).first()
    if record is None:
        return error("Green-space record not found.", 404)
    return JsonResponse(serialize_record(record))


@staff_permission("greenspaces.change_greenspace")
def update_record(request, record_id):
    payload, failure = read_record_json(request, GreenSpaceForm.Meta.fields)
    if failure is not None:
        return failure
    if set(payload) != set(GreenSpaceForm.Meta.fields):
        return error("PUT requires all editable fields. Use empty strings or null for optional values.", 400)
    with transaction.atomic():
        record = GreenSpace.objects.select_for_update().filter(pk=record_id).first()
        if record is None:
            return error("Green-space record not found.", 404)
        form = GreenSpaceForm(payload, instance=record)
        if not form.is_valid():
            return error("Correct the invalid record fields.", 400, fields=form.errors.get_json_data())
        record = form.save()
        return JsonResponse(serialize_record(record))


@staff_permission("greenspaces.delete_greenspace")
def delete_record(request, record_id):
    with transaction.atomic():
        record = GreenSpace.objects.select_for_update().filter(pk=record_id).first()
        if record is None:
            return error("Green-space record not found.", 404)
        record.delete()
    return JsonResponse({"deleted": True, "green_space_id": record_id})


@require_http_methods(["GET", "PUT", "DELETE"])
def record_detail(request, record_id):
    handlers = {"GET": retrieve_record, "PUT": update_record, "DELETE": delete_record}
    return handlers[request.method](request, record_id)
