# ไฟล์ Output สำคัญ

## 1. Landmark และ Amenity

```text
data/processed/landmarks_clean.csv
data/processed/amenities_clean.csv
```

ใช้สำหรับวิเคราะห์จุดสำคัญในพื้นที่ เช่น โรงพยาบาล ห้าง ตลาด สถานที่ราชการ ร้านบริการ และสิ่งอำนวยความสะดวกอื่น ๆ

คอลัมน์สำคัญ:

- `province`, `district`, `sub_district`: พื้นที่ตั้ง
- `name`, `name_en`: ชื่อสถานที่
- `category`: ประเภทสถานที่
- `layer`: ระดับความสำคัญของ POI
- `lat`, `lon`: พิกัด
- `source`: แหล่งที่มา เช่น OpenStreetMap หรือ Google Maps

## 2. Road Output

ไฟล์ถนนมีหลายระดับ:

```text
data/processed/roads.csv
data/processed/roads_enriched.csv
data/processed/roads_final.csv
```

ความหมาย:

- `roads.csv`: ข้อมูลถนนดิบจาก OSM แบบ flatten เป็น CSV
- `roads_enriched.csv`: เพิ่มรายละเอียดจาก Google reverse geocode เพื่อ audit
- `roads_final.csv`: ไฟล์ถนนปลายทางที่ตัด Google detail ออกแล้ว ใช้ต่อได้ง่าย

คอลัมน์ที่ควรใช้ใน `roads_final.csv`:

- `road_name`: ชื่อจาก OSM หรือ `unnamed:<osm_id>`
- `road_ref`: เลขทางหลวง/เลขถนน ถ้ามี
- `road_display_name`: ชื่อสำหรับแสดงผลจริง
- `google_match_status`: สถานะ enrichment เช่น `matched`, `no_route`, `skipped_has_ref`
- `length_km`: ความยาวของ OSM way โดยรวมระยะตาม geometry ของถนน

## 3. Road Intelligence

```text
data/processed/roads_features.csv
data/processed/roads_summary_by_province.csv
data/processed/road_density_by_zone.csv
data/processed/road_intersections.csv
```

ใช้สำหรับสรุปภาพรวมถนน เช่น จำนวน segment, ความยาวรวม, coverage ของชื่อถนน, ref, lanes, surface และ density รอบ zone/anchor

## 4. Cache ที่ไม่ควรลบทิ้งง่าย ๆ

```text
data/raw/google_road_name_cache.json
data/raw/temp_roads_topology/
data/raw/geocode_cache.json
```

ไฟล์เหล่านี้ช่วยลดเวลารันซ้ำและลด API quota โดยเฉพาะ Google road enrichment

