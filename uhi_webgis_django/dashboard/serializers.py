from rest_framework import serializers

from .models import Region, YearlyMetric, UTFVIZone, UrbanizationForecast


class RegionGeoSerializer(serializers.ModelSerializer):
    boundary_geojson = serializers.SerializerMethodField()

    class Meta:
        model = Region
        fields = ["id", "name", "description", "area_km2", "boundary_geojson"]

    def get_boundary_geojson(self, obj):
        import json
        return json.loads(obj.boundary.geojson)


class YearlyMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = YearlyMetric
        fields = ["year", "avg_lst", "avg_ndvi", "avg_ndbi", "avg_ndwi", "heatmap_image",
                  "r_lst_ndbi", "r_lst_ndvi", "corr_n_points"]


class UTFVIZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = UTFVIZone
        fields = ["year", "class_name", "area_km2", "color_hex", "order"]


class UrbanizationForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = UrbanizationForecast
        fields = ["year", "urban_ratio_percent", "is_forecast"]
