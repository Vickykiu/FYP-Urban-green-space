from django.contrib import admin
from django.urls import path
from .views import health
from greenspaces import views as green_views
from greenspaces import upload_views
from greenspaces import public_views
from greenspaces import nearby_views
from greenspaces import coverage_views
from greenspaces import dashboard_views
from greenspaces import report_views

urlpatterns = [
    path('api/public/reports/', report_views.published, name='public-reports'),
    path('api/public/reports/<int:report_id>/', report_views.published_detail, name='public-report-detail'),
    path('api/admin/reports/options/', report_views.options, name='report-options'),
    path('api/admin/reports/drafts/', report_views.drafts, name='report-drafts'),
    path('api/admin/reports/drafts/<int:report_id>/', report_views.draft_detail, name='report-draft-detail'),
    path('api/admin/reports/save-draft/', report_views.save_draft, name='report-save-draft'),
    path('api/admin/reports/generate/', report_views.generate, name='report-generate'),
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/public/green-spaces/", public_views.green_spaces, name="public-green-spaces"),
    path("api/public/green-spaces/<int:record_id>/", public_views.green_space_detail, name="public-green-space-detail"),
    path("api/public/administrative-areas/", public_views.administrative_areas, name="public-administrative-areas"),
    path("api/public/map-options/", public_views.map_options, name="public-map-options"),
    path("api/public/nearby/options/", nearby_views.options, name="public-nearby-options"),
    path("api/public/nearby/", nearby_views.nearby, name="public-nearby"),
    path("api/public/accessibility/", coverage_views.analyse, name="public-accessibility"),
    path("api/public/dashboard/", dashboard_views.dashboard, name="public-dashboard"),
    path("api/public/locations/search/", nearby_views.places, name="public-place-search"),
    path("api/admin/session/", green_views.session, name="admin-session"),
    path("api/admin/lookups/", green_views.lookups, name="admin-lookups"),
    path("api/admin/green-spaces/", green_views.records, name="admin-records"),
    path("api/admin/green-spaces/<int:record_id>/", green_views.record_detail, name="admin-record-detail"),
    path("api/admin/datasets/template/", upload_views.template, name="dataset-template"),
    path("api/admin/datasets/", upload_views.datasets, name="datasets"),
    path("api/admin/datasets/<int:dataset_id>/", upload_views.detail, name="dataset-detail"),
    path("api/admin/datasets/<int:dataset_id>/validate/", upload_views.validate, name="dataset-validate"),
    path("api/admin/datasets/<int:dataset_id>/import/", upload_views.confirm_import, name="dataset-import"),
]
