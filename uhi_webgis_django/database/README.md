# Thư mục `database/` — Cơ sở dữ liệu PostgreSQL/PostGIS của đồ án

CSDL: `uhi_webgis` · PostgreSQL 18 + PostGIS 3.6 · hệ tọa độ WGS84 (SRID 4326).
Bảng được Django tạo tự động từ `dashboard/models.py` qua migration (`python manage.py migrate`);
dữ liệu được nạp bằng `python manage.py load_uhi_data` từ các file kết quả của notebook Google Earth Engine.

| File | Nội dung |
|---|---|
| `schema.sql` | Cấu trúc 10 bảng (CREATE TABLE, khóa chính, khóa ngoại, chỉ mục không gian GIST) — xuất thật từ CSDL bằng `pg_dump --schema-only` |
| `truy_van_mau.sql` | 16 truy vấn SQL/PostGIS mẫu, mỗi câu ứng với một chức năng thật của WebGIS (tìm điểm gần nhất KNN, `ST_Within`, `ST_Contains`, `ST_Union`, `ST_Area`, `ST_AsGeoJSON`, thống kê theo năm/quận-huyện…) |
| `erd.png` | Sơ đồ quan hệ giữa các bảng (ERD) để chèn vào báo cáo |
| `erd.html` | File nguồn vẽ `erd.png` (mở bằng trình duyệt) |

## Chạy truy vấn mẫu trong pgAdmin 4
1. Mở **pgAdmin 4** → bên trái mở `Servers` → `PostgreSQL 18` → `Databases`.
2. Chuột phải database **uhi_webgis** → **Query Tool**.
3. Bấm biểu tượng thư mục (Open File) → chọn `truy_van_mau.sql`.
4. Bôi đen một câu truy vấn → bấm **▶ Execute** (phím F5). Kết quả hiện ở khung *Data Output* bên dưới.

## Xuất lại `schema.sql` sau khi đổi cấu trúc bảng
```
"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -h 127.0.0.1 -U uhi_user -d uhi_webgis --schema-only --no-owner --no-privileges -t "dashboard_*" -f database\schema.sql
```
