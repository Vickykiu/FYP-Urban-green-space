import logging
from functools import wraps

from django.core.paginator import EmptyPage, Paginator
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from config.api import error, read_record_json, staff_permission
from .csv_schema import COLUMNS, CsvFileError
from .datasets import DatasetProblem, create_dataset, import_dataset, validate_dataset, visible_datasets
from .models import ValidationResult

logger = logging.getLogger(__name__)


def dataset_errors(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except DatasetProblem as exc:
            return error(str(exc), exc.status)
        except CsvFileError as exc:
            return error(str(exc), 400)
        except OSError:
            logger.exception("Private dataset staging failed")
            return error("The staged file is unavailable. Check local storage or upload the file again.", 503)
    return wrapped


def serialize_dataset(dataset):
    return {"dataset_id": dataset.pk, "file_name": dataset.file_name,
            "uploaded_at": dataset.uploaded_at.isoformat(), "status": dataset.status,
            "total_records": dataset.total_records, "valid_records": dataset.valid_records,
            "invalid_records": dataset.invalid_records}


def page_number(request):
    try:
        number = int(request.GET.get("page", "1"))
        if number > 0:
            return number
    except ValueError:
        pass
    raise DatasetProblem("page must be a positive integer.")


def validation_detail(dataset, number=1):
    query = ValidationResult.objects.filter(dataset=dataset).order_by("row_number", "validation_id").values(
        "row_number", "field_name", "error_message", "severity", "validation_status",
    )
    paginator = Paginator(query, 100)
    try:
        page = paginator.page(number)
        issues, has_next = list(page.object_list), page.has_next()
    except EmptyPage:
        issues, has_next = [], False
    return {**serialize_dataset(dataset), "issues": issues, "issue_count": paginator.count,
            "page": number, "page_size": 100, "has_next": has_next}


@require_GET
@staff_permission("greenspaces.add_datasetupload")
def template(request):
    response = HttpResponse(",".join(COLUMNS) + "\r\n", content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="green-spaces-template.csv"'
    return response


@staff_permission("greenspaces.add_datasetupload")
@dataset_errors
def upload(request):
    if request.content_type != "multipart/form-data":
        return error("Send a multipart form with one file field named file.", 415)
    files = request.FILES
    if getattr(request, "csv_upload_too_large", False):
        return error("The CSV must be no larger than 5 MiB.", 413)
    if set(files) != {"file"} or len(files.getlist("file")) != 1:
        return error("Upload exactly one CSV using the file field.", 400)
    dataset = create_dataset(request.user, files["file"])
    return JsonResponse(serialize_dataset(dataset), status=201)


@staff_permission("greenspaces.view_datasetupload")
@dataset_errors
def history(request):
    number = page_number(request)
    paginator = Paginator(visible_datasets(request.user), 50)
    try:
        page = paginator.page(number)
        results, has_next = [serialize_dataset(item) for item in page.object_list], page.has_next()
    except EmptyPage:
        results, has_next = [], False
    return JsonResponse({"results": results, "count": paginator.count, "page": number,
                         "page_size": 50, "has_next": has_next})


@require_http_methods(["GET", "POST"])
def datasets(request):
    return history(request) if request.method == "GET" else upload(request)


@require_GET
@staff_permission("greenspaces.view_datasetupload")
@dataset_errors
def detail(request, dataset_id):
    dataset = visible_datasets(request.user).filter(pk=dataset_id).first()
    if dataset is None:
        raise DatasetProblem("Dataset not found.", 404)
    return JsonResponse(validation_detail(dataset, page_number(request)))


@require_POST
@staff_permission("greenspaces.change_datasetupload")
@dataset_errors
def validate(request, dataset_id):
    dataset, token = validate_dataset(request.user, dataset_id)
    return JsonResponse({**validation_detail(dataset), "validation_token": token,
                         "ready_to_import": dataset.status == "validated"})


@require_POST
@staff_permission("greenspaces.change_datasetupload")
@dataset_errors
def confirm_import(request, dataset_id):
    if not request.user.has_perm("greenspaces.add_greenspace"):
        return error("You do not have permission to add green-space records.", 403)
    payload, failure = read_record_json(request, {"validation_token"})
    if failure is not None:
        return failure
    dataset, repeated = import_dataset(request.user, dataset_id, payload.get("validation_token"))
    result = validation_detail(dataset)
    if dataset.status != "imported":
        return error("Validation changed. Correct the listed issues before import.", 409, dataset=result)
    return JsonResponse({**result, "already_imported": repeated, "imported_records": dataset.valid_records})
