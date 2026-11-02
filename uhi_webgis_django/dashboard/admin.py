from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import (
    Region, YearlyMetric, UTFVIZone, UrbanizationForecast, HeatSamplePoint,
    District, DistrictYearStat, GridCell, LSTForecast, ForecastBacktest,
)


@admin.register(Region)
class RegionAdmin(GISModelAdmin):
    list_display = ("name", "area_km2")


@admin.register(YearlyMetric)
class YearlyMetricAdmin(admin.ModelAdmin):
    list_display = ("year", "avg_lst", "avg_ndvi", "avg_ndbi", "avg_ndwi")
    ordering = ("year",)


@admin.register(UTFVIZone)
class UTFVIZoneAdmin(admin.ModelAdmin):
    list_display = ("year", "class_name", "area_km2", "order")
    list_filter = ("year",)


@admin.register(UrbanizationForecast)
class UrbanizationForecastAdmin(admin.ModelAdmin):
    list_display = ("year", "urban_ratio_percent", "is_forecast")


@admin.register(HeatSamplePoint)
class HeatSamplePointAdmin(GISModelAdmin):
    list_display = ("year", "lst", "ndvi", "ndbi")
    list_filter = ("year",)


@admin.register(District)
class DistrictAdmin(GISModelAdmin):
    list_display = ("name_vi", "name_gaul", "province", "code")
    list_filter = ("province",)
