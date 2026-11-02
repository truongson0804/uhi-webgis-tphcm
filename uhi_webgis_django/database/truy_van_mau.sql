-- =====================================================================
--  ĐỒ ÁN: WebGIS Đảo nhiệt đô thị TP.HCM 2020–2026
--  Các truy vấn SQL / PostGIS mẫu trên CSDL uhi_webgis (PostgreSQL + PostGIS)
--
--  Cách chạy: mở pgAdmin 4 -> chuột phải database "uhi_webgis" -> Query Tool
--             -> dán từng câu (hoặc cả file) -> bấm nút ▶ (F5).
--  Mỗi truy vấn tương ứng với một chức năng thật của WebGIS (ghi ở dòng "Dùng ở").
--  Tất cả số liệu là dữ liệu thật nạp từ notebook Google Earth Engine.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Kiểm tra phiên bản PostgreSQL và PostGIS
-- ---------------------------------------------------------------------
SELECT version()               AS postgresql,
       postgis_lib_version()   AS postgis;


-- ---------------------------------------------------------------------
-- 2. Số dòng dữ liệu trong từng bảng của đồ án
-- ---------------------------------------------------------------------
SELECT 'dashboard_region'               AS bang, COUNT(*) AS so_dong FROM dashboard_region
UNION ALL SELECT 'dashboard_yearlymetric',         COUNT(*) FROM dashboard_yearlymetric
UNION ALL SELECT 'dashboard_utfvizone',            COUNT(*) FROM dashboard_utfvizone
UNION ALL SELECT 'dashboard_urbanizationforecast', COUNT(*) FROM dashboard_urbanizationforecast
UNION ALL SELECT 'dashboard_heatsamplepoint',      COUNT(*) FROM dashboard_heatsamplepoint
UNION ALL SELECT 'dashboard_district',             COUNT(*) FROM dashboard_district
UNION ALL SELECT 'dashboard_districtyearstat',     COUNT(*) FROM dashboard_districtyearstat
UNION ALL SELECT 'dashboard_gridcell',             COUNT(*) FROM dashboard_gridcell
UNION ALL SELECT 'dashboard_lstforecast',          COUNT(*) FROM dashboard_lstforecast
UNION ALL SELECT 'dashboard_forecastbacktest',     COUNT(*) FROM dashboard_forecastbacktest;


-- ---------------------------------------------------------------------
-- 3. Các cột hình học (không gian) trong CSDL — kiểu và hệ tọa độ
-- ---------------------------------------------------------------------
SELECT f_table_name AS bang, f_geometry_column AS cot, type AS kieu_hinh_hoc, srid
FROM geometry_columns
WHERE f_table_name LIKE 'dashboard_%'
ORDER BY f_table_name;


-- ---------------------------------------------------------------------
-- 4. Chỉ số trung bình toàn vùng theo năm + hệ số tương quan Pearson
--    Dùng ở: biểu đồ xu hướng, bảng số liệu, ô KPI trang tổng quan
-- ---------------------------------------------------------------------
SELECT year                   AS nam,
       ROUND(avg_lst::numeric, 2)  AS lst_tb_c,
       ROUND(avg_ndvi::numeric, 3) AS ndvi_tb,
       ROUND(avg_ndbi::numeric, 3) AS ndbi_tb,
       ROUND(avg_ndwi::numeric, 3) AS ndwi_tb,
       r_lst_ndbi, r_lst_ndvi, corr_n_points AS so_diem_mau
FROM dashboard_yearlymetric
ORDER BY year;


-- ---------------------------------------------------------------------
-- 5. Diện tích vùng nghiên cứu tính từ hình học thật (km²)
--    ST_Area trên kiểu geography -> diện tích trên mặt cầu, đơn vị m²
-- ---------------------------------------------------------------------
SELECT name,
       ROUND((ST_Area(boundary::geography) / 1e6)::numeric, 1) AS dien_tich_km2,
       ST_NPoints(boundary) AS so_dinh
FROM dashboard_region;


-- ---------------------------------------------------------------------
-- 6. Ghép (ST_Union) 38 quận/huyện thành ranh giới vùng nghiên cứu
--    Dùng ở: API /api/map/aoi/ — viền vẽ chồng lên ảnh LST ở trang tổng quan
-- ---------------------------------------------------------------------
SELECT COUNT(*)                                                         AS so_quan_huyen,
       ROUND((ST_Area(ST_Union(boundary)::geography) / 1e6)::numeric, 1) AS dien_tich_km2,
       ST_GeometryType(ST_Union(boundary))                              AS kieu
FROM dashboard_district;


-- ---------------------------------------------------------------------
-- 7. TÌM ĐIỂM MẪU PIXEL GẦN NHẤT với một vị trí (truy vấn KNN)
--    Dùng ở: bấm lên bản đồ / tìm tọa độ -> API /api/heat-points/nearest/
--    Toán tử <-> dùng chỉ mục GIST để tìm nhanh; ST_Distance(geography) ra mét.
--    Ví dụ vị trí: Chợ Bến Thành (10.7725, 106.6980), năm 2026
-- ---------------------------------------------------------------------
SELECT id,
       ROUND(ST_Y(location)::numeric, 5) AS lat,
       ROUND(ST_X(location)::numeric, 5) AS lon,
       ROUND(lst::numeric, 2)  AS lst_c,
       ROUND(ndvi::numeric, 3) AS ndvi,
       ROUND(ndbi::numeric, 3) AS ndbi,
       n_obs                   AS so_anh_hop_le,
       ROUND(ST_Distance(location::geography,
                         ST_SetSRID(ST_MakePoint(106.6980, 10.7725), 4326)::geography)::numeric, 0) AS cach_m
FROM dashboard_heatsamplepoint
WHERE year = 2026
ORDER BY location <-> ST_SetSRID(ST_MakePoint(106.6980, 10.7725), 4326)
LIMIT 3;


-- ---------------------------------------------------------------------
-- 8. Ô lưới 1 km nằm trong mỗi quận/huyện (ST_Within) — năm 2026
--    Dùng ở: lệnh nạp dữ liệu gán quận/huyện cho từng ô; lọc "Khu vực" trang Bản đồ
-- ---------------------------------------------------------------------
SELECT d.name_vi                   AS quan_huyen,
       d.province                  AS tinh_cu,
       COUNT(g.id)                 AS so_o_1km,
       ROUND(AVG(g.lst)::numeric, 2) AS lst_tb_o_luoi
FROM dashboard_district d
JOIN dashboard_gridcell g
  ON g.year = 2026 AND ST_Within(g.center, d.boundary)
GROUP BY d.name_vi, d.province
ORDER BY lst_tb_o_luoi DESC
LIMIT 10;


-- ---------------------------------------------------------------------
-- 9. Xếp hạng quận/huyện nóng nhất năm 2026 (thống kê reduceRegions từ GEE)
--    Dùng ở: bảng "Xếp hạng quận/huyện" trang Bản đồ, ô nóng nhất/mát nhất
-- ---------------------------------------------------------------------
SELECT RANK() OVER (ORDER BY s.lst DESC) AS hang,
       d.name_vi                          AS quan_huyen,
       d.province                         AS tinh_cu,
       ROUND(s.lst::numeric, 2)           AS lst_c,
       ROUND(s.ndvi::numeric, 3)          AS ndvi,
       ROUND(s.ndbi::numeric, 3)          AS ndbi
FROM dashboard_districtyearstat s
JOIN dashboard_district d ON d.id = s.district_id
WHERE s.year = 2026
ORDER BY s.lst DESC
LIMIT 10;


-- ---------------------------------------------------------------------
-- 10. Quận/huyện thay đổi LST nhiều nhất giữa 2020 và 2026
-- ---------------------------------------------------------------------
SELECT d.name_vi AS quan_huyen,
       ROUND(a.lst::numeric, 2)           AS lst_2020,
       ROUND(b.lst::numeric, 2)           AS lst_2026,
       ROUND((b.lst - a.lst)::numeric, 2) AS chenh_lech
FROM dashboard_district d
JOIN dashboard_districtyearstat a ON a.district_id = d.id AND a.year = 2020
JOIN dashboard_districtyearstat b ON b.district_id = d.id AND b.year = 2026
ORDER BY ABS(b.lst - a.lst) DESC
LIMIT 10;


-- ---------------------------------------------------------------------
-- 11. Trung bình LST theo tỉnh cũ, tính từ các ô lưới 1 km (JOIN theo khóa ngoại)
--     Dùng ở: API /api/map/history/?scope=province:...
-- ---------------------------------------------------------------------
SELECT g.year AS nam, d.province AS tinh_cu,
       ROUND(AVG(g.lst)::numeric, 2) AS lst_tb,
       COUNT(*)                      AS so_o
FROM dashboard_gridcell g
JOIN dashboard_district d ON d.id = g.district_id
GROUP BY g.year, d.province
ORDER BY d.province, g.year;


-- ---------------------------------------------------------------------
-- 12. Tỉ lệ diện tích từng mức UTFVI theo năm (trên phần có dữ liệu)
--     Dùng ở: mục 05 "Phân vùng cường độ đảo nhiệt"
-- ---------------------------------------------------------------------
SELECT year AS nam, class_name AS muc_utfvi, area_km2,
       ROUND((100 * area_km2 / SUM(area_km2) OVER (PARTITION BY year))::numeric, 1) AS ti_le_pct
FROM dashboard_utfvizone
WHERE class_name <> 'Không có dữ liệu'
ORDER BY year, "order";


-- ---------------------------------------------------------------------
-- 13. Thống kê điểm mẫu pixel theo năm: nóng nhất, số điểm ≥ 40°C,
--     số điểm chỉ có 1–2 ảnh Landsat hợp lệ (độ tin cậy thấp)
--     Dùng ở: khối "Điểm mẫu pixel 100 m" trang Bản đồ
-- ---------------------------------------------------------------------
SELECT year AS nam,
       COUNT(*)                                      AS so_diem,
       ROUND(MAX(lst)::numeric, 1)                   AS lst_max,
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY lst)::numeric, 1) AS lst_p95,
       COUNT(*) FILTER (WHERE lst >= 40)             AS so_diem_tren_40c,
       COUNT(*) FILTER (WHERE n_obs <= 2)            AS so_diem_it_quan_trac
FROM dashboard_heatsamplepoint
GROUP BY year
ORDER BY year;


-- ---------------------------------------------------------------------
-- 14. Điểm mẫu nằm trong một quận cụ thể (ST_Contains) — ví dụ Quận 1, năm 2026
-- ---------------------------------------------------------------------
SELECT d.name_vi, COUNT(p.id) AS so_diem_mau, ROUND(AVG(p.lst)::numeric, 2) AS lst_tb
FROM dashboard_district d
LEFT JOIN dashboard_heatsamplepoint p
       ON p.year = 2026 AND ST_Contains(d.boundary, p.location)
WHERE d.name_vi IN ('Quận 1', 'Quận 3', 'Bình Thạnh', 'Cần Giờ')
GROUP BY d.name_vi;


-- ---------------------------------------------------------------------
-- 15. Dự báo LST 2027–2030 và kiểm định ngược năm 2026
--     Dùng ở: tab "Dự báo" và "Kiểm định 2026" trang Bản đồ
-- ---------------------------------------------------------------------
SELECT year AS nam, ROUND(lst_linear::numeric, 2) AS tuyen_tinh,
       ROUND(lst_poly::numeric, 2) AS da_thuc_bac_2, r2_linear, r2_poly
FROM dashboard_lstforecast ORDER BY year;

SELECT model, train_years, ROUND(pred_2026::numeric, 2) AS du_bao_2026,
       ROUND(actual_2026::numeric, 2) AS quan_trac_2026, ROUND(error::numeric, 2) AS sai_so
FROM dashboard_forecastbacktest;


-- ---------------------------------------------------------------------
-- 16. Xuất ranh giới một quận/huyện ra GeoJSON (định dạng web hiển thị bản đồ)
--     Dùng ở: API /api/map/districts/
-- ---------------------------------------------------------------------
SELECT name_vi, LEFT(ST_AsGeoJSON(boundary, 5), 200) || '...' AS geojson_rut_gon
FROM dashboard_district
WHERE name_vi = 'Quận 1';
