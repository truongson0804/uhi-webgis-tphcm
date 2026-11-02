from django.contrib.gis.db import models


class Region(models.Model):
    """Vùng nghiên cứu (ranh giới TP.HCM sau sáp nhập, 01/07/2025)."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    # Ranh giới xấp xỉ (bounding polygon) của vùng nghiên cứu, lưu dạng PostGIS Polygon.
    # Lưu ý: đây là hình chữ nhật bao ngoài xấp xỉ dùng để minh họa trên bản đồ;
    # ranh giới hành chính chính xác được lấy trực tiếp từ FAO GAUL trong notebook GEE.
    boundary = models.PolygonField(srid=4326)
    area_km2 = models.FloatField(help_text="Diện tích ước tính (km²)")

    def __str__(self):
        return self.name


class YearlyMetric(models.Model):
    """Chỉ số môi trường trung bình toàn vùng nghiên cứu theo từng năm."""

    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="yearly_metrics")
    year = models.IntegerField(unique=True)
    avg_lst = models.FloatField(help_text="Nhiệt độ bề mặt trung bình (°C)")
    avg_ndvi = models.FloatField(help_text="Chỉ số thực vật trung bình")
    avg_ndbi = models.FloatField(help_text="Chỉ số xây dựng trung bình")
    avg_ndwi = models.FloatField(help_text="Chỉ số nước trung bình")
    # Ảnh bản đồ nhiệt render sẵn từ notebook (nếu có), lưu đường dẫn static.
    heatmap_image = models.CharField(max_length=300, blank=True)
    # Hệ số tương quan Pearson theo năm, tính trong notebook trên ~2.000 điểm mẫu
    # (sample scale=100, seed=42) — file tuong_quan_theo_nam.csv. Null nếu chưa tính.
    r_lst_ndbi = models.FloatField(null=True, blank=True, help_text="Pearson r giữa LST và NDBI")
    r_lst_ndvi = models.FloatField(null=True, blank=True, help_text="Pearson r giữa LST và NDVI")
    corr_n_points = models.IntegerField(null=True, blank=True, help_text="Số điểm mẫu hợp lệ dùng tính r")

    class Meta:
        ordering = ["year"]

    def __str__(self):
        return f"{self.year}: LST={self.avg_lst:.2f}°C"


class UTFVIZone(models.Model):
    """Phân vùng cường độ đảo nhiệt theo chỉ số UTFVI cho một năm cụ thể."""

    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="utfvi_zones")
    year = models.IntegerField()
    class_name = models.CharField(max_length=50)
    area_km2 = models.FloatField()
    color_hex = models.CharField(max_length=7, default="#9F1C2E")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["year", "order"]

    def __str__(self):
        return f"{self.year} - {self.class_name}: {self.area_km2:.1f} km²"


class UrbanizationForecast(models.Model):
    """Kết quả mô phỏng chuỗi Markov về tỉ lệ đô thị hóa."""

    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="urbanization_forecasts")
    year = models.IntegerField(unique=True)
    urban_ratio_percent = models.FloatField(help_text="Tỉ lệ diện tích đô thị hóa (%)")
    is_forecast = models.BooleanField(default=False, help_text="True nếu là giá trị ngoại suy, False nếu là giá trị quan trắc")

    class Meta:
        ordering = ["year"]

    def __str__(self):
        kind = "dự báo" if self.is_forecast else "quan trắc"
        return f"{self.year} ({kind}): {self.urban_ratio_percent:.1f}%"


class HeatSamplePoint(models.Model):
    """Điểm mẫu pixel thật (LST/NDVI/NDBI) xuất từ notebook bằng
    ee.Image.sample(..., scale=100, numPixels=2000, seed=42, geometries=True)."""

    year = models.IntegerField(db_index=True)
    location = models.PointField(srid=4326)
    lst = models.FloatField(help_text="Nhiệt độ bề mặt (°C)")
    ndvi = models.FloatField()
    ndbi = models.FloatField()
    n_obs = models.IntegerField(null=True, blank=True, help_text="Số ảnh Landsat hợp lệ tại pixel (sau che mây)")
    # Quận/huyện GAUL chứa điểm (gán bằng ST_Within khi nạp dữ liệu); null nếu nằm ngoài các quận/huyện
    district = models.ForeignKey("District", null=True, blank=True, on_delete=models.SET_NULL, related_name="sample_points")

    class Meta:
        ordering = ["year", "id"]

    def __str__(self):
        return f"{self.year} ({self.location.y:.4f}, {self.location.x:.4f}): {self.lst:.1f}°C"


class District(models.Model):
    """Quận/huyện theo FAO GAUL 2015 cấp 2 (cùng bộ dữ liệu với AOI của notebook).

    Lưu ý: ranh giới năm 2015 — một số đơn vị đã đổi sau đó, và cấp huyện bị bãi bỏ từ 01/07/2025.
    """

    code = models.IntegerField(unique=True, help_text="ADM2_CODE của GAUL")
    name_gaul = models.CharField(max_length=100)
    name_vi = models.CharField(max_length=100)
    province = models.CharField(max_length=100, help_text="Tỉnh/thành cũ (ADM1_NAME)")
    boundary = models.MultiPolygonField(srid=4326)

    class Meta:
        ordering = ["province", "name_vi"]

    def __str__(self):
        return f"{self.name_vi} ({self.province})"


class DistrictYearStat(models.Model):
    """Trung bình toàn bộ pixel 100 m trong quận/huyện theo năm (reduceRegions, notebook mục 9d)."""

    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name="stats")
    year = models.IntegerField()
    lst = models.FloatField(null=True)
    ndvi = models.FloatField(null=True)
    ndbi = models.FloatField(null=True)
    ndwi = models.FloatField(null=True)

    class Meta:
        ordering = ["year", "district"]
        unique_together = [("district", "year")]


class GridCell(models.Model):
    """Ô lưới 1 km: trung bình các pixel 30 m hợp lệ trong ô (reduceResolution, notebook mục 9d)."""

    year = models.IntegerField(db_index=True)
    center = models.PointField(srid=4326)
    lst = models.FloatField(null=True)
    ndvi = models.FloatField(null=True)
    ndbi = models.FloatField(null=True)
    ndwi = models.FloatField(null=True)
    coverage = models.FloatField(help_text="Tỉ lệ diện tích ô có pixel LST hợp lệ (0–1)")
    district = models.ForeignKey(District, null=True, blank=True, on_delete=models.SET_NULL, related_name="cells")

    class Meta:
        ordering = ["year", "id"]


class LSTForecast(models.Model):
    """Dự báo LST trung bình toàn vùng 2027–2030 (notebook mục 11, xuất ở 11b)."""

    year = models.IntegerField(unique=True)
    lst_linear = models.FloatField()
    lst_poly = models.FloatField()
    r2_linear = models.FloatField()
    r2_poly = models.FloatField()

    class Meta:
        ordering = ["year"]


class ForecastBacktest(models.Model):
    """Kiểm định ngược: huấn luyện trên 2020–2025, dự báo 2026, so với quan trắc thật (notebook 11b)."""

    model = models.CharField(max_length=50, unique=True)
    train_years = models.CharField(max_length=20)
    pred_2026 = models.FloatField()
    actual_2026 = models.FloatField()
    error = models.FloatField()


class ForecastSeries(models.Model):
    """Dự báo 2027–2030 + kiểm định 2026 cho một chỉ số ở một phạm vi (notebook mục 11c).

    scope: 'all' (toàn vùng) hoặc 'gaul:<ADM2_CODE>' (quận/huyện); index: lst/ndvi/ndbi/ndwi.
    forecast: [{"year", "linear", "poly"}, ...]
    """

    scope = models.CharField(max_length=30)
    scope_name = models.CharField(max_length=100)
    index = models.CharField(max_length=10)
    district = models.ForeignKey("District", null=True, blank=True, on_delete=models.CASCADE, related_name="forecasts")
    forecast = models.JSONField()
    r2_linear = models.FloatField()
    r2_poly = models.FloatField()
    bt_pred_linear = models.FloatField()
    bt_pred_poly = models.FloatField()
    actual_2026 = models.FloatField(null=True)

    class Meta:
        unique_together = [("scope", "index")]
