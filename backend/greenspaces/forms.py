"""Manual record entry for FR10; bulk dataset import belongs to a later stage."""
from django import forms
from django.contrib.gis.geos import Point

from .models import GreenSpace


class GreenSpaceForm(forms.ModelForm):
    class Meta:
        model = GreenSpace
        fields = (
            "name", "area", "category", "area_size", "facilities",
            "description", "latitude", "longitude",
        )
        labels = {"area": "Administrative area", "area_size": "Area (ha)"}
        help_texts = {
            "latitude": "WGS84 latitude, between -90 and 90; up to 6 decimal places.",
            "longitude": "WGS84 longitude, between -180 and 180; up to 6 decimal places.",
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Enter a green-space name.")
        return name

    def clean(self):
        cleaned = super().clean()
        lat = cleaned.get("latitude")
        lon = cleaned.get("longitude")
        geometry = self.instance.geometry
        preserves_boundary = geometry is not None and geometry.geom_type in {"Polygon", "MultiPolygon"}
        if (lat is None) != (lon is None):
            self.add_error("latitude", "Provide both latitude and longitude, or leave both empty for a polygon record.")
        if not preserves_boundary:
            if lat is None:
                self.add_error("latitude", "Latitude is required for a point record.")
            if lon is None:
                self.add_error("longitude", "Longitude is required for a point record.")
            if lat is not None and lon is not None:
                self.instance.geometry = Point(float(lon), float(lat), srid=4326)
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Geometry is deliberately excluded from the editable fields. Validate
        # it explicitly before saving; ModelForm excludes it from field checks.
        instance.full_clean()
        if commit:
            instance.save()
            self.save_m2m()
        return instance
