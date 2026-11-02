import json
import os

from django.conf import settings
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    Region, YearlyMetric, UTFVIZone, UrbanizationForecast, HeatSamplePoint,
    District, DistrictYearStat, GridCell, LSTForecast, ForecastBacktest,
)
from .serializers import (
    RegionGeoSerializer,
    YearlyMetricSerializer,
    UTFVIZoneSerializer,
    UrbanizationForecastSerializer,
)


def dashboard_view(request):
    """Trang WebGIS chính — HTML template render bằng Django, dữ liệu lấy qua API."""
    return render(request, "dashboard/index.html")


@api_view(["GET"])
def api_region(request):
    """GET /api/region/ — ranh giới vùng nghiên cứu (GeoJSON) từ PostGIS."""
    region = Region.objects.first()
    if not region:
        return Response({"detail": "Chưa có dữ liệu Region."}, status=404)
    return Response(RegionGeoSerializer(region).data)


@api_view(["GET"])
def api_yearly_metrics(request):
    """GET /api/yearly-metrics/ — chuỗi LST/NDVI/NDBI/NDWI theo năm (2020-2026)."""
    qs = YearlyMetric.objects.all().order_by("year")
    return Response(YearlyMetricSerializer(qs, many=True).data)


@api_view(["GET"])
def api_yearly_metric_detail(request, year):
    """GET /api/yearly-metrics/<year>/ — chỉ số + trạng thái ảnh bản đồ của một năm cụ thể."""
    try:
        m = YearlyMetric.objects.get(year=year)
    except YearlyMetric.DoesNotExist:
        return Response({"detail": f"Không có dữ liệu cho năm {year}."}, status=404)

    data = YearlyMetricSerializer(m).data
    static_path = os.path.join(settings.BASE_DIR, "dashboard", "static", m.heatmap_image)
    data["heatmap_available"] = os.path.exists(static_path)
    return Response(data)


@api_view(["GET"])
def api_utfvi_zones(request):
    """GET /api/utfvi-zones/?year=2026 — phân vùng cường độ đảo nhiệt UTFVI."""
    year = request.GET.get("year", 2026)
    qs = UTFVIZone.objects.filter(year=year).order_by("order")
    return Response(UTFVIZoneSerializer(qs, many=True).data)


@api_view(["GET"])
def api_urbanization(request):
    """GET /api/urbanization/ — kết quả mô phỏng chuỗi Markov (tỉ lệ đô thị hóa)."""
    qs = UrbanizationForecast.objects.all().order_by("year")
    return Response(UrbanizationForecastSerializer(qs, many=True).data)


def _utfvi_class(lst, lst_mean):
    """Phân mức UTFVI = (LST - LST_TB) / LST_TB, đúng ngưỡng Bước 8 của notebook."""
    utfvi = (lst - lst_mean) / lst_mean
    bins = [(0, "Không UHI"), (0.005, "Yếu"), (0.010, "Trung bình"),
            (0.015, "Mạnh"), (0.020, "Rất mạnh")]
    for upper, name in bins:
        if utfvi < upper:
            return utfvi, name
    return utfvi, "Nghiêm trọng"


@api_view(["GET"])
def api_heat_points(request):
    """GET /api/heat-points/?year=2026 — điểm mẫu pixel thật + thống kê tính từ chính các điểm đó.

    points: [[lat, lon, lst, ndvi, ndbi, n_obs, district_id], ...] (gọn để vẽ heatmap).
    """
    year = int(request.GET.get("year", 2026))
    qs = HeatSamplePoint.objects.filter(year=year)
    pts = [[p.location.y, p.location.x, p.lst, p.ndvi, p.ndbi, p.n_obs, p.district_id] for p in qs]
    if not pts:
        return Response({"year": year, "count": 0, "points": [], "stats": None})

    lsts = sorted(p[2] for p in pts)
    n = len(lsts)
    hottest = max(pts, key=lambda p: p[2])
    stats = {
        "count": n,
        "lst_min": lsts[0],
        "lst_max": lsts[-1],
        "lst_mean": sum(lsts) / n,
        "lst_p95": lsts[min(n - 1, int(round(0.95 * (n - 1))))],
        "n_over_40": sum(1 for v in lsts if v >= 40),
        # số điểm mà pixel chỉ có 1–2 ảnh Landsat hợp lệ sau che mây (trung vị kém tin cậy)
        "n_low_obs": sum(1 for p in pts if p[5] is not None and p[5] <= 2),
        "n_with_obs": sum(1 for p in pts if p[5] is not None),
        "hottest": {"lat": hottest[0], "lon": hottest[1], "lst": hottest[2],
                    "ndvi": hottest[3], "ndbi": hottest[4], "n_obs": hottest[5]},
    }
    return Response({"year": year, "count": n, "points": pts, "stats": stats})


@api_view(["GET"])
def api_heat_point_nearest(request):
    """GET /api/heat-points/nearest/?lat=..&lon=..&year=2026 — điểm mẫu thật gần nhất (PostGIS).

    Không nội suy: trả về đúng giá trị của điểm mẫu gần nhất kèm khoảng cách tới vị trí bấm.
    """
    from django.contrib.gis.db.models.functions import Distance
    from django.contrib.gis.geos import Point

    try:
        lat = float(request.GET["lat"])
        lon = float(request.GET["lon"])
    except (KeyError, ValueError):
        return Response({"detail": "Cần tham số lat và lon hợp lệ."}, status=400)
    year = int(request.GET.get("year", 2026))

    target = Point(lon, lat, srid=4326)
    p = (HeatSamplePoint.objects.filter(year=year)
         .annotate(dist=Distance("location", target))
         .order_by("dist").first())
    if not p:
        return Response({"detail": f"Không có điểm mẫu cho năm {year}."}, status=404)

    data = {
        "year": year, "lat": p.location.y, "lon": p.location.x,
        "lst": p.lst, "ndvi": p.ndvi, "ndbi": p.ndbi, "n_obs": p.n_obs,
        "distance_m": p.dist.m,
    }
    metric = YearlyMetric.objects.filter(year=year).first()
    if metric:
        utfvi, cls = _utfvi_class(p.lst, metric.avg_lst)
        data.update({"utfvi": utfvi, "utfvi_class": cls, "lst_mean_year": metric.avg_lst})
    return Response(data)


# ======================= Trang Bản đồ tương tác (/ban-do/) =======================

GRID_LAYERS = ("lst", "ndvi", "ndbi", "ndwi")


def map_view(request):
    """Trang bản đồ riêng: lưới 1 km, lọc theo năm/khu vực/lớp, xếp hạng quận/huyện, dự báo."""
    return render(request, "dashboard/map.html")


def _percentile(sorted_vals, q):
    if not sorted_vals:
        return None
    return sorted_vals[min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1))))]


_RANGE_ALL_CACHE = {}


def _range_all_years():
    """Khoảng p2–p98 của từng lớp trên toàn bộ ô lưới 2020–2026 (thang màu "cố định toàn kỳ")."""
    n = GridCell.objects.count()
    if _RANGE_ALL_CACHE.get("n") != n:
        rng = {}
        for layer in GRID_LAYERS:
            vals = sorted(v for v in GridCell.objects.values_list(layer, flat=True) if v is not None)
            rng[layer] = [_percentile(vals, 0.02), _percentile(vals, 0.98)]
        _RANGE_ALL_CACHE.clear()
        _RANGE_ALL_CACHE.update({"n": n, "range": rng})
    return _RANGE_ALL_CACHE["range"]


@api_view(["GET"])
def api_map_grid(request):
    """GET /api/map/grid/?year=2026 — ô lưới 1 km (notebook mục 9d).

    cells: [[lat, lon, lst, ndvi, ndbi, ndwi, coverage, district_id], ...]
    """
    year = int(request.GET.get("year", 2026))
    rows = GridCell.objects.filter(year=year).values_list(
        "center", "lst", "ndvi", "ndbi", "ndwi", "coverage", "district_id")
    cells = [[c.y, c.x, lst, ndvi, ndbi, ndwi, cov, did] for c, lst, ndvi, ndbi, ndwi, cov, did in rows]
    metric = YearlyMetric.objects.filter(year=year).first()
    return Response({
        "year": year, "cell_m": 1000, "count": len(cells), "cells": cells,
        "lst_mean_year": metric.avg_lst if metric else None,
        "range_all": _range_all_years() if cells else None,
        "years_available": sorted(set(GridCell.objects.values_list("year", flat=True))),
    })


@api_view(["GET"])
def api_map_districts(request):
    """GET /api/map/districts/ — ranh giới quận/huyện GAUL 2015 (GeoJSON)."""
    feats = [{
        "type": "Feature", "id": d.id,
        "properties": {"id": d.id, "name_vi": d.name_vi, "name_gaul": d.name_gaul, "province": d.province},
        "geometry": json.loads(d.boundary.geojson),
    } for d in District.objects.all()]
    return Response({"type": "FeatureCollection", "features": feats})


@api_view(["GET"])
def api_map_district_stats(request):
    """GET /api/map/district-stats/?year=2026 — trung bình toàn bộ pixel trong từng quận/huyện."""
    year = int(request.GET.get("year", 2026))
    qs = DistrictYearStat.objects.filter(year=year).select_related("district")
    return Response([{
        "id": s.district_id, "name_vi": s.district.name_vi, "province": s.district.province,
        "lst": s.lst, "ndvi": s.ndvi, "ndbi": s.ndbi, "ndwi": s.ndwi,
    } for s in qs])


@api_view(["GET"])
def api_map_history(request):
    """GET /api/map/history/?scope=all | province:<ADM1_NAME> | district:<id>

    all      -> YearlyMetric (reduceRegion toàn vùng, notebook mục 5)
    district -> DistrictYearStat (reduceRegions, notebook mục 9d)
    province -> trung bình các ô lưới 1 km thuộc tỉnh (tính trên web từ GridCell)
    """
    from django.db.models import Avg

    scope = request.GET.get("scope", "all")
    if scope == "all":
        series = [{"year": m.year, "lst": m.avg_lst, "ndvi": m.avg_ndvi, "ndbi": m.avg_ndbi, "ndwi": m.avg_ndwi}
                  for m in YearlyMetric.objects.order_by("year")]
        source = "Trung bình toàn vùng (reduceRegion, notebook mục 5)"
    elif scope.startswith("district:"):
        did = int(scope.split(":", 1)[1])
        series = [{"year": s.year, "lst": s.lst, "ndvi": s.ndvi, "ndbi": s.ndbi, "ndwi": s.ndwi}
                  for s in DistrictYearStat.objects.filter(district_id=did).order_by("year")]
        source = "Trung bình quận/huyện (reduceRegions, notebook mục 9d)"
    elif scope.startswith("province:"):
        prov = scope.split(":", 1)[1]
        agg = (GridCell.objects.filter(district__province=prov).values("year")
               .annotate(lst=Avg("lst"), ndvi=Avg("ndvi"), ndbi=Avg("ndbi"), ndwi=Avg("ndwi")).order_by("year"))
        series = list(agg)
        source = "Trung bình các ô lưới 1 km thuộc tỉnh (tính trên web)"
    else:
        return Response({"detail": "scope không hợp lệ"}, status=400)
    return Response({"scope": scope, "source": source, "series": series})


@api_view(["GET"])
def api_map_forecast_series(request):
    """GET /api/map/forecast-series/?scope=all|district:<id>&index=lst|ndvi|ndbi|ndwi

    Dự báo + kiểm định 2026 theo chỉ số và phạm vi (notebook mục 11c), kèm chuỗi quan trắc 2020–2026.
    """
    from .models import ForecastSeries

    scope = request.GET.get("scope", "all")
    index = request.GET.get("index", "lst")
    if index not in ("lst", "ndvi", "ndbi", "ndwi"):
        return Response({"available": False, "reason": "index"})
    qs = ForecastSeries.objects.filter(index=index)
    if scope == "all":
        fs = qs.filter(scope="all").first()
        observed = [{"year": m.year, "value": getattr(m, f"avg_{index}")} for m in YearlyMetric.objects.order_by("year")]
    elif scope.startswith("district:"):
        did = int(scope.split(":", 1)[1])
        fs = qs.filter(district_id=did).first()
        observed = [{"year": s.year, "value": getattr(s, index)}
                    for s in DistrictYearStat.objects.filter(district_id=did).order_by("year")]
    else:
        return Response({"available": False, "reason": "scope"})
    if not fs:
        return Response({"available": False, "reason": "missing"})
    return Response({
        "available": True, "scope": scope, "scope_name": fs.scope_name, "index": index,
        "observed": observed, "forecast": fs.forecast,
        "r2_linear": fs.r2_linear, "r2_poly": fs.r2_poly,
        "backtest": {"pred_linear": fs.bt_pred_linear, "pred_poly": fs.bt_pred_poly, "actual_2026": fs.actual_2026},
    })


@api_view(["GET"])
def api_map_forecast(request):
    """GET /api/map/forecast/ — dự báo LST 2027–2030 + kiểm định 2026 (notebook mục 11, 11b)."""
    return Response({
        "observed": [{"year": m.year, "lst": m.avg_lst} for m in YearlyMetric.objects.order_by("year")],
        "forecast": [{"year": f.year, "lst_linear": f.lst_linear, "lst_poly": f.lst_poly,
                      "r2_linear": f.r2_linear, "r2_poly": f.r2_poly} for f in LSTForecast.objects.all()],
        "backtest": [{"model": b.model, "train_years": b.train_years, "pred_2026": b.pred_2026,
                      "actual_2026": b.actual_2026, "error": b.error} for b in ForecastBacktest.objects.all()],
    })


_AOI_CACHE = {}


@api_view(["GET"])
def api_map_aoi(request):
    """GET /api/map/aoi/ — ranh giới AOI đúng như notebook dùng: hợp (ST_Union) 38 quận/huyện FAO GAUL 2015.

    Dùng để vẽ viền chồng lên ảnh LST (ảnh được clip theo chính AOI GAUL này).
    """
    from django.contrib.gis.db.models import Union

    n = District.objects.count()
    if _AOI_CACHE.get("n") != n:
        geom = District.objects.aggregate(u=Union("boundary"))["u"]
        _AOI_CACHE.clear()
        _AOI_CACHE.update({"n": n, "geojson": json.loads(geom.geojson) if geom else None})
    if not _AOI_CACHE["geojson"]:
        return Response({"detail": "Chưa có quận/huyện GAUL."}, status=404)
    return Response({"type": "Feature", "properties": {"source": "FAO GAUL 2015 cấp 2 (hợp 38 quận/huyện)"},
                     "geometry": _AOI_CACHE["geojson"]})


UTFVI_LEVELS = ["Không UHI", "Yếu", "Trung bình", "Mạnh", "Rất mạnh", "Nghiêm trọng"]


@api_view(["GET"])
def api_map_utfvi_history(request):
    """GET /api/map/utfvi-history/?scope=all | province:<ADM1_NAME> | district:<id>

    Tỉ lệ % diện tích (trên phần có dữ liệu) của 6 mức UTFVI theo từng năm.
    all      -> bảng UTFVIZone (notebook mục 8b, tính trên pixel 100 m toàn vùng)
    khác     -> đếm ô lưới 1 km trong khu vực, UTFVI = (LST ô − LST TB năm toàn vùng) / LST TB năm,
                cùng ngưỡng 0 / 0,005 / 0,010 / 0,015 / 0,020 như notebook mục 8.
    """
    scope = request.GET.get("scope", "all")
    series = []
    if scope == "all":
        for y in sorted(set(UTFVIZone.objects.values_list("year", flat=True))):
            rows = {z.class_name: z.area_km2 for z in UTFVIZone.objects.filter(year=y) if z.class_name in UTFVI_LEVELS}
            tot = sum(rows.values()) or 1
            series.append({"year": y, "shares": [100 * rows.get(c, 0) / tot for c in UTFVI_LEVELS], "n": round(tot)})
        source = "Diện tích theo pixel 100 m toàn vùng (notebook mục 8b)"
        unit = "km²"
    else:
        qs = GridCell.objects.filter(lst__isnull=False)
        if scope.startswith("district:"):
            qs = qs.filter(district_id=int(scope.split(":", 1)[1]))
        elif scope.startswith("province:"):
            qs = qs.filter(district__province=scope.split(":", 1)[1])
        else:
            return Response({"detail": "scope không hợp lệ"}, status=400)
        means = dict(YearlyMetric.objects.values_list("year", "avg_lst"))
        bins = [0, 0.005, 0.010, 0.015, 0.020]
        by_year = {}
        for y, lst in qs.values_list("year", "lst"):
            m = means.get(y)
            if not m:
                continue
            u = (lst - m) / m
            k = sum(1 for b in bins if u >= b)
            by_year.setdefault(y, [0] * 6)[k] += 1
        for y in sorted(by_year):
            c = by_year[y]; tot = sum(c) or 1
            series.append({"year": y, "shares": [100 * x / tot for x in c], "n": tot})
        source = "Đếm ô lưới 1 km trong khu vực, so với LST trung bình năm toàn vùng (cùng ngưỡng notebook mục 8)"
        unit = "ô 1 km"
    return Response({"scope": scope, "levels": UTFVI_LEVELS, "source": source, "unit": unit, "series": series})


@api_view(["GET"])
def api_data_quality(request):
    """GET /api/data-quality/ — chất lượng dữ liệu theo năm (báo cáo mục 3.2).

    n_points: số điểm đo mẫu hợp lệ; good_pct: % điểm có ≥ 3 ảnh Landsat hợp lệ sau che mây;
    nodata_km2: diện tích không phân loại được UTFVI do bị che mây (notebook mục 8b).
    """
    from django.db.models import Count, Q

    rows = (HeatSamplePoint.objects.values("year")
            .annotate(n=Count("id"), good=Count("id", filter=Q(n_obs__gt=2)), with_obs=Count("id", filter=Q(n_obs__isnull=False)))
            .order_by("year"))
    nodata = dict(UTFVIZone.objects.filter(class_name="Không có dữ liệu").values_list("year", "area_km2"))
    return Response([{
        "year": r["year"], "n_points": r["n"],
        "good_pct": 100 * r["good"] / r["with_obs"] if r["with_obs"] else None,
        "nodata_km2": nodata.get(r["year"]),
    } for r in rows])
