from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import AdministrativeArea, GreenSpace, GreenSpaceCategory
from .forms import GreenSpaceForm


@admin.register(AdministrativeArea)
class AdministrativeAreaAdmin(GISModelAdmin):
    list_display = ("area_name", "area_type")
    search_fields = ("area_name",)


@admin.register(GreenSpaceCategory)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("category_name",)
    search_fields = ("category_name",)


@admin.register(GreenSpace)
class GreenSpaceAdmin(admin.ModelAdmin):
    form = GreenSpaceForm
    list_display = ("name", "area", "category")
    list_filter = ("area", "category")
    search_fields = ("name", "description")
    list_select_related = ("area", "category")
    readonly_fields = ("dataset",)
    fields = (*GreenSpaceForm.Meta.fields, "dataset")


admin.site.site_header = "Petaling GIS administration"
admin.site.site_title = "Petaling GIS"
admin.site.index_title = "Green-space data management"
