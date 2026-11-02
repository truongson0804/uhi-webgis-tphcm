# Đồ án: WebGIS Đảo nhiệt đô thị TP.HCM 2020–2026

## Bối cảnh
Đồ án chuyên ngành Tin học Môi trường của sinh viên (MSSV 1250080162, khóa 2023–2027).
Phân tích đảo nhiệt đô thị (UHI) TP.HCM giai đoạn 2020–2026, xây dựng thành web app thật
bằng Django + PostgreSQL/PostGIS + Leaflet.js + Chart.js (không phải trang tĩnh HTML giả lập).

**Nguyên tắc xuyên suốt của đồ án: KHÔNG bịa số liệu.** Mọi chỉ số, ranh giới, biểu đồ
hiển thị trên web đều phải là dữ liệu thật lấy từ notebook phân tích (Google Earth Engine),
không suy diễn hay tô vẽ thêm cho đẹp. Khi không có dữ liệu thật cho một phần nào đó, phải
nói rõ trong UI thay vì giả vờ có.

## Kiến trúc
- Backend: Django 5 + Django REST Framework
- Database: PostgreSQL + PostGIS (ranh giới vùng nghiên cứu lưu dạng `PolygonField` thật,
  không phải hình chữ nhật bbox gần đúng)
- Frontend: `dashboard/templates/dashboard/index.html` — HTML/CSS thuần + Leaflet.js (bản đồ)
  + Chart.js (biểu đồ), gọi dữ liệu qua REST API, không hard-code số liệu trong JS
- Nguồn dữ liệu gốc: notebook `UHI_TPHCM_2020_2026.ipynb` (Google Earth Engine) +
  `bang_tong_hop_UHI_TPHCM_2020_2026.csv`

## Các quyết định/thay đổi quan trọng đã làm

1. **Ranh giới vùng nghiên cứu là hình học thật**, không phải bbox xấp xỉ — gộp
   (dissolve) ranh giới cấp tỉnh thật của TP.HCM cũ + Bình Dương cũ + Bà Rịa-Vũng Tàu cũ,
   lấy từ geoBoundaries (open data, cùng nguồn FAO GAUL mà notebook GEE dùng). File:
   `dashboard/data/region_boundary_real.geojson`.

2. **Phát hiện và xử lý minh bạch một mismatch dữ liệu quan trọng**: notebook GEE gốc chỉ
   tính LST/NDVI/NDBI/NDWI trên AOI = TP.HCM cũ (`FAO/GAUL/2015/level1`, `ADM1_NAME='Ho Chi
   Minh City'`), KHÔNG mở rộng sang Bình Dương/Bà Rịa-Vũng Tàu — dù ranh giới hiển thị trên
   bản đồ là 3 tỉnh gộp (theo narrative "sau sáp nhập 01/07/2025" trong báo cáo). Đã ghi rõ
   cảnh báo này trong `Region.description` (model) và `README.md`, KHÔNG được xóa bỏ cảnh báo
   này trừ khi chạy lại notebook với AOI mở rộng thật.

3. **Heatmap thật mới nhất**: xuất 1.984 điểm mẫu thật (tọa độ + LST/NDVI/NDBI) từ
   `ee.Image.sample(..., geometries=True)` trong notebook (cell mục 9, năm 2026) →
   `dashboard/data/lst_points_2026.geojson` → API `GET /api/heat-points/` → render bằng
   Leaflet.heat (`dashboard/static/dashboard/vendor/leaflet-heat.js`, cài qua `npm pack
   leaflet.heat`). Toggle "Heatmap điểm thật (2026)" trong Layer Management — CHỈ hoạt động
   với năm 2026 vì chỉ năm đó có dữ liệu điểm thật; tự khóa/tắt khi chọn năm khác. Thang màu
   heatmap cố định max=45°C để khớp đúng legend (99% điểm nằm trong 25–45°C).

4. Trước heatmap điểm, có lớp tô 1 màu cho cả vùng ranh giới theo giá trị LST trung bình
   thật của năm đang chọn (hàm `lstToColor()` nội suy theo đúng thang màu legend) — đây là
   fallback trung thực khi chưa có dữ liệu điểm, KHÔNG suy diễn loang màu giả.

5. **Hệ số tương quan Pearson theo từng năm** (LST~NDBI, LST~NDVI): ban đầu notebook chỉ
   tính r cho năm 2026; đã thêm cell sau mục 9 lặp qua `yearly_images` (2020–2026), cùng
   cách lấy mẫu (2.000 điểm, scale=100, seed=42) → `dashboard/data/tuong_quan_theo_nam.csv`
   → trường `r_lst_ndbi` / `r_lst_ndvi` / `corr_n_points` của `YearlyMetric` (nạp bằng
   `load_uhi_data`) → trả qua `/api/yearly-metrics/`. Ô KPI r đổi theo năm đang chọn; năm
   nào chưa có r (null) thì hiển thị "Chưa tính", không suy diễn.

6. **(18/10/2026: đã chuyển sang trang `/ban-do/`, mục 03 trang tổng quan chỉ còn tóm tắt + nút mở trang bản đồ; tìm tọa độ, lớp điểm mẫu, điểm nóng nhất kèm `n_obs` nằm ở `/ban-do/`)** Trước đây: mục 03 là dashboard GIS (bố cục: Layer Management | bản đồ | cột Phân tích & Thống kê).
   1.984 điểm mẫu năm 2026 lưu trong PostGIS (model `HeatSamplePoint`, `PointField`), nạp bằng
   `load_uhi_data` từ `dashboard/data/lst_points_2026.geojson`. API:
   `GET /api/heat-points/?year=` (điểm + thống kê max/P95/số điểm ≥40°C tính từ chính các điểm) và
   `GET /api/heat-points/nearest/?lat=&lon=&year=` (điểm mẫu gần nhất bằng truy vấn khoảng cách
   PostGIS, không nội suy; kèm UTFVI = (LST − LST_TB năm)/LST_TB năm theo ngưỡng Bước 8).
   Lớp: heatmap LST (Leaflet.heat, bán kính ≈1,6 km theo mặt đất để vệt không chồng lên nhau),
   điểm mẫu tô theo LST/NDVI/NDBI, ranh giới. Tìm theo tọa độ, thanh trạng thái tọa độ con trỏ,
   thước tỉ lệ. Năm chưa có điểm mẫu thì khoá lớp điểm và quay về tô 1 màu theo LST trung bình.
   KHÔNG đưa vào các phần của mẫu tham khảo không có dữ liệu thật (NO2, lượng mưa, R²/RMSE mô hình,
   "feature importance", tên/xếp hạng quận, mùa khô/mưa, "live GPS").

7. **Che mây chặt hơn & chạy lại notebook (04/10/2026)**: phát hiện điểm LST 67°C trên vườn cây
   (NDVI 0,52) ở Châu Đức — không hợp lý vật lý. `mask_l8sr` (cell 7) nay che thêm QA_PIXEL bit 0/1/2
   (fill, viền mây, mây ti) và pixel có `ST_QA` > 5 K; composite có thêm band `n_obs` (số ảnh hợp lệ).
   Chạy lại toàn bộ → mọi số liệu thay đổi nhẹ (LST 2025: 31,36 → 33,53°C; r 2026: 0,63 → 0,72).
   Điểm 67°C cũ bị che hoàn toàn. Xuất điểm mẫu cho cả 7 năm (`lst_points_<năm>.geojson`, mục 9b)
   và `utfvi_2026.csv` (loader đọc CSV, không chép tay). Còn 2 pixel nóng 61–68°C lặp lại mọi năm:
   (10,4588; 107,0654) sát tổ hợp công nghiệp lớn ven biển Long Sơn, và (10,8233; 106,7642) khuôn
   viên trường học ở Thủ Đức — chưa kiểm chứng được nguyên nhân, nhiều giá trị chỉ có 1–2 ảnh hợp lệ.
   Web hiển thị `n_obs` và cảnh báo "ít quan trắc" khi `n_obs` ≤ 2. Dữ liệu cũ lưu ở `_backup/`.

8. **Trang Bản đồ tương tác riêng `/ban-do/`** (`dashboard/templates/dashboard/map.html`): sidebar bộ lọc
   (lớp LST/UTFVI/NDVI/NDBI/NDWI, khu vực toàn vùng/tỉnh cũ/quận-huyện, năm 2020–2026, lọc ô ≥ 50% dữ
   liệu, thang màu tự động/cố định), bản đồ lưới ô 1 km, KPI, xếp hạng quận/huyện, tab Biểu đồ lịch sử /
   Dự báo / Kiểm định 2026 / Giới thiệu và hạn chế, xuất CSV. Dữ liệu từ notebook:
   - mục **9d**: lưới 1 km (`reduceResolution` mean pixel 30 m, kèm `coverage`) → `lst_grid_1km_<năm>.geojson`
     → model `GridCell`; quận/huyện FAO GAUL 2015 cấp 2 → `ranh_gioi_quan_huyen_gaul2015.geojson` (model
     `District`) + `thong_ke_quan_huyen.csv` (`reduceRegions`, model `DistrictYearStat`).
   - mục **11b**: `du_bao_lst.csv` (model `LSTForecast`) và `kiem_dinh_2026.csv` — huấn luyện 2020–2025,
     dự báo 2026, so với quan trắc (model `ForecastBacktest`).
   API: `/api/map/grid/`, `/api/map/districts/`, `/api/map/district-stats/`, `/api/map/history/`,
   `/api/map/forecast/`. Thời gian theo **năm** (ảnh ghép mùa khô 01–03), KHÔNG có dữ liệu theo tháng.

9. **Ảnh bản đồ LST cho cả 7 năm** (notebook mục 7b): `getThumbURL` từ Earth Engine, cùng thang màu `lst_vis` 25–45°C của mục 7, khung đất liền (không gồm Côn Đảo) → `dashboard/static/dashboard/maps/lst_<năm>.png`. Thay ảnh chụp tay geemap năm 2026 cũ (lưu ở `_backup/static_cu/`).

10. Nhiều cải tiến UI khác: so sánh 2 năm bất kỳ, basemap Dark/Vệ tinh/Ẩn, nút fullscreen,
   thanh điều hướng nhanh (side-nav), popup/tooltip ranh giới, fix bug z-index panel bị che,
   fix white-flash khi tile load.

## Môi trường local của người dùng (Windows)

- Đang set up chạy local lần đầu trên máy Windows (trước đó code được phát triển/test trong
  sandbox Linux, nay copy sang Windows chạy thật).
- Vướng mắc đã gặp và cách fix:
  - **GeoDjango cần GDAL** — Windows không tự cài qua pip được, phải cài qua OSGeo4W
    (https://trac.osgeo.org/osgeo4w/), chọn "Express Web-GIS Install". Sau khi cài, phải
    set biến `GDAL_LIBRARY_PATH` trong `settings.py` là **biến settings Django bình
    thường** (KHÔNG phải `os.environ[...]`) trỏ đúng tên file `gdalXXX.dll` thật tìm thấy
    trong thư mục `bin` của OSGeo4W (số phiên bản DLL thay đổi tùy lần cài, ví dụ
    `gdal313.dll`). `PROJ_LIB` và `PATH` thì set qua `os.environ` bình thường.
  - **PostgreSQL**: cần tạo user + database khớp với `DATABASES` trong `settings.py`
    (qua pgAdmin 4 hoặc psql) — superuser `postgres` + mật khẩu đặt lúc cài PostgreSQL,
    tạo database (ví dụ `uhi_webgis`) với owner phù hợp, rồi chạy `CREATE EXTENSION
    postgis;` trong Query Tool của đúng database đó trước khi `python manage.py migrate`.
  - Thư mục project: `D:\Do An Chuyen Nganh\uhi_webgis_django\` (25/10/2026 đã gỡ cấp lồng
    `uhi_webgis_django\uhi_webgis_django\` cũ; `venv` đã được tạo lại phần khởi động theo đường dẫn mới).

## Việc đang làm dở / cần tiếp tục
- Đang set up chạy local trên Windows lần đầu (GDAL + PostgreSQL), đã gần xong, có thể còn
  vướng vài lỗi cấu hình nhỏ — xử lý tiếp theo kiểu debug thông thường (đọc traceback, sửa
  đúng dòng báo lỗi).
- Khi sửa `settings.py`, PHẢI xem kỹ file hiện tại trước khi đề xuất đổi, tránh đè mất dòng
  import có sẵn (đã từng bị mất `from pathlib import Path` do paste đè).

## Quy tắc khi làm việc tiếp
- Giữ nguyên nguyên tắc KHÔNG bịa số liệu/tính năng giả ở mọi thay đổi sau này.
- Khi thêm tính năng mới cần dữ liệu không có sẵn, phải hỏi lại hoặc tìm dữ liệu thật
  (ví dụ cách đã làm với ranh giới geoBoundaries và heatmap điểm mẫu từ GEE), không tự
  chế số liệu để lấp chỗ trống.
- Người dùng không rành thuật ngữ kỹ thuật sâu — khi hướng dẫn thao tác, giải thích từng
  bước rõ ràng, cụ thể, kiểu "bấm vào đâu, gõ gì".
