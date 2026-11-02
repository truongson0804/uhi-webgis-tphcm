import csv
import json
from pathlib import Path

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Point
from django.core.management.base import BaseCommand

from dashboard.models import (
    Region, YearlyMetric, UTFVIZone, UrbanizationForecast, HeatSamplePoint,
    District, DistrictYearStat, GridCell, LSTForecast, ForecastBacktest, ForecastSeries,
)

CSV_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "bang_tong_hop_UHI_TPHCM_2020_2026.csv"
BOUNDARY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "region_boundary_real.geojson"
# Hệ số tương quan Pearson LST~NDBI / LST~NDVI theo từng năm, xuất từ notebook
# (cell sau mục 9: lặp qua yearly_images, sample 2.000 điểm, scale=100, seed=42).
CORR_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "tuong_quan_theo_nam.csv"
# Điểm mẫu pixel thật theo năm (tọa độ + LST/NDVI/NDBI [+ n_obs]), xuất từ notebook mục 9b bằng
# ee.Image.sample(..., scale=100, numPixels=2000, seed=42, geometries=True).
# Nạp mọi file lst_points_<năm>.geojson có trong thư mục data.
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
# Diện tích từng mức UTFVI năm 2026, xuất từ notebook mục 8 (cột: year, order, class_name, area_km2).
# Ưu tiên utfvi_theo_nam.csv (notebook mục 8b, mọi năm 2020–2026, kèm dòng "Không có dữ liệu");
# nếu chưa có thì dùng utfvi_2026.csv (mục 8, chỉ năm 2026).
UTFVI_CSV_PATH = DATA_DIR / "utfvi_theo_nam.csv"
if not UTFVI_CSV_PATH.exists():
    UTFVI_CSV_PATH = DATA_DIR / "utfvi_2026.csv"
UTFVI_COLORS = {
    "Không UHI": "#0E9488", "Yếu": "#EAB308", "Trung bình": "#EA9C08",
    "Mạnh": "#C77B12", "Rất mạnh": "#C2410C", "Nghiêm trọng": "#9F1C2E",
    "Không có dữ liệu": "#4E5A78",
}

# ---- Dữ liệu cho trang Bản đồ (notebook mục 9d và 11b) ----
DISTRICTS_PATH = DATA_DIR / "ranh_gioi_quan_huyen_gaul2015.geojson"
DISTRICT_STATS_PATH = DATA_DIR / "thong_ke_quan_huyen.csv"
FORECAST_PATH = DATA_DIR / "du_bao_lst.csv"
BACKTEST_PATH = DATA_DIR / "kiem_dinh_2026.csv"
# Dự báo mọi chỉ số, toàn vùng + từng quận/huyện (notebook mục 11c)
SERIES_PATH = DATA_DIR / "du_bao_theo_chi_so.csv"
# Tên tiếng Việt để hiển thị cho tên GAUL (không dấu, tiếng Anh). Chỉ là nhãn, không đổi ranh giới.
DISTRICT_NAME_VI = {
    "District 1": "Quận 1", "District 2": "Quận 2", "District 3": "Quận 3", "District 4": "Quận 4",
    "District 5": "Quận 5", "District 6": "Quận 6", "District 7": "Quận 7", "District 8": "Quận 8",
    "District 9": "Quận 9", "District 10": "Quận 10", "District 11": "Quận 11", "District 12": "Quận 12",
    "Binh Chanh": "Bình Chánh", "Binh Tan": "Bình Tân", "Binh Thanh": "Bình Thạnh", "Can Gio": "Cần Giờ",
    "Cu Chi": "Củ Chi", "Go Vap": "Gò Vấp", "Hoc Mon": "Hóc Môn", "Nha Be": "Nhà Bè",
    "Phu Nhuan": "Phú Nhuận", "Tan Binh": "Tân Bình", "Tan Phu": "Tân Phú", "Thu Duc": "Thủ Đức",
    "Ben Cat": "Bến Cát", "Dau Tieng": "Dầu Tiếng", "Di An": "Dĩ An", "Phu Giao": "Phú Giáo",
    "Tan Uyen": "Tân Uyên", "Thu Dau Mot Township": "Thủ Dầu Một", "Thuan An": "Thuận An",
    "Ba Ria Township": "Bà Rịa", "Chau Duc": "Châu Đức", "Con Dao": "Côn Đảo", "Long Dat": "Long Đất",
    "Tan Thanh": "Tân Thành", "Vung Tau City": "Vũng Tàu", "Xuyen Moc": "Xuyên Mộc",
}

# Phân vùng UTFVI năm 2026 (km²) — kết quả từ Bước 8 của notebook phân tích với cách che mây CŨ
# (chỉ bit mây + bóng mây). Chỉ dùng khi chưa có utfvi_2026.csv từ lần chạy notebook mới.
UTFVI_2026 = [
    ("Không UHI", 3449.0, "#0E9488"),
    ("Yếu", 120.4, "#EAB308"),
    ("Trung bình", 118.5, "#EA9C08"),
    ("Mạnh", 119.1, "#C77B12"),
    ("Rất mạnh", 113.6, "#C2410C"),
    ("Nghiêm trọng", 2698.0, "#9F1C2E"),
]

# Kết quả mô phỏng chuỗi Markov (tỉ lệ diện tích đô thị hóa), từ notebook.
URBANIZATION = [
    (2021, 14.8, False),
    (2026, 17.6, False),
    (2030, 19.1, True),
]

# Ranh giới hành chính THẬT (không phải hình chữ nhật gần đúng) của vùng nghiên cứu
# sau sáp nhập 01/07/2025 — gộp (dissolve) ranh giới cấp tỉnh thật của TP.HCM cũ,
# Bình Dương cũ và Bà Rịa - Vũng Tàu cũ, lấy từ geoBoundaries (open data, cùng nguồn
# gốc FAO GAUL mà notebook GEE dùng). File này được tạo sẵn trong region_boundary_real.geojson.
#
# LƯU Ý QUAN TRỌNG: các chỉ số LST/NDVI/NDBI/NDWI theo năm (bảng YearlyMetric) chỉ được
# tính trên vùng TP.HCM cũ trong notebook GEE gốc (biến aoi = FAO/GAUL/2015/level1,
# ADM1_NAME='Ho Chi Minh City') — KHÔNG bao phủ Bình Dương/Bà Rịa-Vũng Tàu. Ranh giới
# hiển thị trên bản đồ (3 tỉnh gộp) rộng hơn vùng thực sự đã tính chỉ số. Xem README.


def _load_region_boundary():
    with open(BOUNDARY_PATH, encoding="utf-8") as f:
        geojson = json.load(f)
    geom = GEOSGeometry(json.dumps(geojson["geometry"]), srid=4326)
    if geom.geom_type == "MultiPolygon":
        # Region.boundary là PolygonField — lấy đa giác lớn nhất nếu union ra MultiPolygon
        geom = max(geom, key=lambda g: g.area)
    return geom


class Command(BaseCommand):
    help = "Nạp dữ liệu thật (CSV + kết quả notebook) vào database PostGIS"

    def handle(self, *args, **options):
        region, created = Region.objects.update_or_create(
            name="TP. Hồ Chí Minh (sau sáp nhập 01/07/2025)",
            defaults={
                "description": (
                    "Vùng nghiên cứu gồm TP.HCM cũ, tỉnh Bình Dương cũ và tỉnh Bà Rịa - "
                    "Vũng Tàu cũ, hợp nhất theo Nghị quyết sáp nhập đơn vị hành chính "
                    "ngày 01/07/2025. Ranh giới hiển thị là ranh giới hành chính thật "
                    "(gộp từ dữ liệu cấp tỉnh geoBoundaries/FAO GAUL), không phải hình "
                    "chữ nhật xấp xỉ. Lưu ý: các chỉ số LST/NDVI/NDBI/NDWI theo năm chỉ "
                    "được tính trên vùng TP.HCM cũ (theo notebook GEE gốc), chưa mở rộng "
                    "sang Bình Dương/Bà Rịa-Vũng Tàu."
                ),
                "boundary": _load_region_boundary(),
                "area_km2": 6162.6,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Region {'tạo mới' if created else 'cập nhật'}: {region}"))

        if not CSV_PATH.exists():
            self.stderr.write(self.style.ERROR(f"Không tìm thấy file CSV tại {CSV_PATH}"))
            return

        count = 0
        with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                year = int(row["year"])
                YearlyMetric.objects.update_or_create(
                    year=year,
                    defaults={
                        "region": region,
                        "avg_lst": float(row["LST"]),
                        "avg_ndvi": float(row["NDVI"]),
                        "avg_ndbi": float(row["NDBI"]),
                        "avg_ndwi": float(row["NDWI"]),
                        "heatmap_image": f"dashboard/maps/lst_{year}.png",   # notebook mục 7b
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Đã nạp {count} dòng YearlyMetric từ CSV"))

        if CORR_PATH.exists():
            corr_count = 0
            with open(CORR_PATH, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    corr_count += YearlyMetric.objects.filter(year=int(row["year"])).update(
                        r_lst_ndbi=float(row["r_ndbi"]),
                        r_lst_ndvi=float(row["r_ndvi"]),
                        corr_n_points=int(row["n_points"]),
                    )
            self.stdout.write(self.style.SUCCESS(f"Đã nạp hệ số tương quan cho {corr_count} năm"))
        else:
            self.stderr.write(self.style.WARNING(f"Không thấy {CORR_PATH} — bỏ qua hệ số tương quan"))

        if UTFVI_CSV_PATH.exists():
            with open(UTFVI_CSV_PATH, newline="", encoding="utf-8-sig") as f:
                utfvi = [(r["class_name"], float(r["area_km2"]), int(r["order"]), int(r["year"]))
                         for r in csv.DictReader(f)]
            source = UTFVI_CSV_PATH.name
        else:
            utfvi = [(name, area, order, 2026) for order, (name, area, _) in enumerate(UTFVI_2026)]
            source = "số liệu cũ trong code (chưa có utfvi_2026.csv)"
        for year in {u[3] for u in utfvi}:
            UTFVIZone.objects.filter(year=year).delete()
        for name, area, order, year in utfvi:
            UTFVIZone.objects.create(
                region=region, year=year, class_name=name, area_km2=area,
                color_hex=UTFVI_COLORS.get(name, "#9F1C2E"), order=order,
            )
        self.stdout.write(self.style.SUCCESS(f"Đã nạp {len(utfvi)} phân vùng UTFVI từ {source}"))

        for year, ratio, is_forecast in URBANIZATION:
            UrbanizationForecast.objects.update_or_create(
                year=year, defaults={
                    "region": region, "urban_ratio_percent": ratio, "is_forecast": is_forecast,
                }
            )
        self.stdout.write(self.style.SUCCESS(f"Đã nạp {len(URBANIZATION)} mốc mô phỏng đô thị hóa"))

        for path in sorted(DATA_DIR.glob("lst_points_*.geojson")):
            try:
                year = int(path.stem.rsplit("_", 1)[1])
            except ValueError:
                continue
            with open(path, encoding="utf-8") as f:
                features = json.load(f)["features"]
            objs = []
            for feat in features:
                props = feat["properties"]
                if any(props.get(k) is None for k in ("LST", "NDVI", "NDBI")):
                    continue
                lon, lat = feat["geometry"]["coordinates"][:2]
                objs.append(HeatSamplePoint(
                    year=year, location=Point(lon, lat, srid=4326),
                    lst=props["LST"], ndvi=props["NDVI"], ndbi=props["NDBI"],
                    n_obs=props.get("n_obs"),
                ))
            HeatSamplePoint.objects.filter(year=year).delete()
            HeatSamplePoint.objects.bulk_create(objs, batch_size=500)
            self.stdout.write(self.style.SUCCESS(f"Đã nạp {len(objs)} điểm mẫu thật năm {year}"))

        self._load_map_page_data()

        self.stdout.write(self.style.SUCCESS("Hoàn tất nạp dữ liệu thật vào PostGIS."))

    def _load_map_page_data(self):
        """Lưới 1 km, quận/huyện GAUL 2015, dự báo và kiểm định — dùng cho trang /ban-do/."""
        if DISTRICTS_PATH.exists():
            with open(DISTRICTS_PATH, encoding="utf-8") as f:
                feats = json.load(f)["features"]
            keep = []
            for feat in feats:
                p = feat["properties"]
                geom = GEOSGeometry(json.dumps(feat["geometry"]), srid=4326)
                if geom.geom_type == "Polygon":
                    geom = MultiPolygon(geom, srid=4326)
                elif geom.geom_type == "GeometryCollection":
                    polys = [g for g in geom if g.geom_type in ("Polygon", "MultiPolygon")]
                    geom = MultiPolygon([q for g in polys for q in (g if g.geom_type == "MultiPolygon" else [g])], srid=4326)
                District.objects.update_or_create(code=int(p["ADM2_CODE"]), defaults={
                    "name_gaul": p["ADM2_NAME"], "name_vi": DISTRICT_NAME_VI.get(p["ADM2_NAME"], p["ADM2_NAME"]),
                    "province": p["ADM1_NAME"], "boundary": geom,
                })
                keep.append(int(p["ADM2_CODE"]))
            District.objects.exclude(code__in=keep).delete()
            self.stdout.write(self.style.SUCCESS(f"Đã nạp {len(keep)} quận/huyện (GAUL 2015)"))
        else:
            self.stderr.write(self.style.WARNING(f"Không thấy {DISTRICTS_PATH.name} — bỏ qua quận/huyện"))

        if DISTRICT_STATS_PATH.exists():
            by_code = {d.code: d for d in District.objects.all()}
            n = 0
            with open(DISTRICT_STATS_PATH, newline="", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    d = by_code.get(int(float(r["ADM2_CODE"])))
                    if not d:
                        continue
                    val = lambda k: float(r[k]) if r.get(k) not in (None, "") else None
                    DistrictYearStat.objects.update_or_create(district=d, year=int(r["year"]), defaults={
                        "lst": val("LST"), "ndvi": val("NDVI"), "ndbi": val("NDBI"), "ndwi": val("NDWI"),
                    })
                    n += 1
            self.stdout.write(self.style.SUCCESS(f"Đã nạp {n} dòng thống kê quận/huyện theo năm"))

        districts = list(District.objects.all())
        # Gán quận/huyện cho từng điểm đo mẫu (tâm điểm nằm trong ranh giới — ST_Within)
        HeatSamplePoint.objects.update(district=None)
        for d in districts:
            HeatSamplePoint.objects.filter(location__within=d.boundary).update(district=d)
        self.stdout.write(self.style.SUCCESS(
            f"Đã gán quận/huyện cho {HeatSamplePoint.objects.filter(district__isnull=False).count()} "
            f"/ {HeatSamplePoint.objects.count()} điểm đo mẫu"))
        for path in sorted(DATA_DIR.glob("lst_grid_1km_*.geojson")):
            year = int(path.stem.rsplit("_", 1)[1])
            with open(path, encoding="utf-8") as f:
                features = json.load(f)["features"]
            GridCell.objects.filter(year=year).delete()
            objs = []
            for feat in features:
                p = feat["properties"]
                lon, lat = feat["geometry"]["coordinates"][:2]
                objs.append(GridCell(
                    year=year, center=Point(lon, lat, srid=4326), lst=p.get("LST"), ndvi=p.get("NDVI"),
                    ndbi=p.get("NDBI"), ndwi=p.get("NDWI"), coverage=p.get("coverage") or 0,
                ))
            GridCell.objects.bulk_create(objs, batch_size=1000)
            # Gán quận/huyện cho từng ô bằng truy vấn không gian PostGIS (tâm ô nằm trong ranh giới)
            for d in districts:
                GridCell.objects.filter(year=year, center__within=d.boundary).update(district=d)
            n_in = GridCell.objects.filter(year=year, district__isnull=False).count()
            self.stdout.write(self.style.SUCCESS(f"Đã nạp {len(objs)} ô lưới 1 km năm {year} ({n_in} ô thuộc một quận/huyện)"))

        if FORECAST_PATH.exists():
            with open(FORECAST_PATH, newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            LSTForecast.objects.all().delete()
            for r in rows:
                LSTForecast.objects.create(year=int(r["year"]), lst_linear=float(r["lst_linear"]),
                                           lst_poly=float(r["lst_poly"]), r2_linear=float(r["r2_linear"]),
                                           r2_poly=float(r["r2_poly"]))
            self.stdout.write(self.style.SUCCESS(f"Đã nạp {len(rows)} năm dự báo LST"))

        if BACKTEST_PATH.exists():
            with open(BACKTEST_PATH, newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            ForecastBacktest.objects.all().delete()
            for r in rows:
                ForecastBacktest.objects.create(model=r["model"], train_years=r["train_years"],
                                                pred_2026=float(r["pred_2026"]), actual_2026=float(r["actual_2026"]),
                                                error=float(r["error"]))
            self.stdout.write(self.style.SUCCESS(f"Đã nạp {len(rows)} dòng kiểm định 2026"))

        if SERIES_PATH.exists():
            by_code = {d.code: d for d in District.objects.all()}
            groups = {}
            with open(SERIES_PATH, newline="", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    groups.setdefault((r["scope"], r["index"]), []).append(r)
            ForecastSeries.objects.all().delete()
            for (scope, index), rs in groups.items():
                r0 = rs[0]
                fnum = lambda v: float(v) if v not in ("", None, "nan") else None
                ForecastSeries.objects.create(
                    scope=scope, scope_name=r0["scope_name"], index=index,
                    district=by_code.get(int(scope.split(":")[1])) if scope.startswith("gaul:") else None,
                    forecast=[{"year": int(r["year"]), "linear": float(r["linear"]), "poly": float(r["poly"])} for r in rs],
                    r2_linear=float(r0["r2_linear"]), r2_poly=float(r0["r2_poly"]),
                    bt_pred_linear=float(r0["bt_pred_linear"]), bt_pred_poly=float(r0["bt_pred_poly"]),
                    actual_2026=fnum(r0["actual_2026"]),
                )
            self.stdout.write(self.style.SUCCESS(f"Đã nạp {len(groups)} chuỗi dự báo theo chỉ số/quận-huyện"))
