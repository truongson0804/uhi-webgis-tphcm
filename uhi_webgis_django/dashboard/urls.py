from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("api/region/", views.api_region, name="api-region"),
    path("api/yearly-metrics/", views.api_yearly_metrics, name="api-yearly-metrics"),
    path("api/yearly-metrics/<int:year>/", views.api_yearly_metric_detail, name="api-yearly-metric-detail"),
    path("api/utfvi-zones/", views.api_utfvi_zones, name="api-utfvi-zones"),
    path("api/urbanization/", views.api_urbanization, name="api-urbanization"),
    path("api/heat-points/", views.api_heat_points, name="api-heat-points"),
    path("api/heat-points/nearest/", views.api_heat_point_nearest, name="api-heat-point-nearest"),
    path("ban-do/", views.map_view, name="map"),
    path("api/map/grid/", views.api_map_grid, name="api-map-grid"),
    path("api/map/districts/", views.api_map_districts, name="api-map-districts"),
    path("api/map/district-stats/", views.api_map_district_stats, name="api-map-district-stats"),
    path("api/map/history/", views.api_map_history, name="api-map-history"),
    path("api/map/utfvi-history/", views.api_map_utfvi_history, name="api-map-utfvi-history"),
    path("api/data-quality/", views.api_data_quality, name="api-data-quality"),
    path("api/map/forecast/", views.api_map_forecast, name="api-map-forecast"),
    path("api/map/forecast-series/", views.api_map_forecast_series, name="api-map-forecast-series"),
    path("api/map/aoi/", views.api_map_aoi, name="api-map-aoi"),
]
