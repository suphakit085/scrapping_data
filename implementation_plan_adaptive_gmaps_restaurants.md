# Adaptive Google Maps Grid Search สำหรับ Restaurants

## Summary

แก้ข้อจำกัด Google Maps ที่แสดงผลประมาณ 120 ร้านต่อ search ด้วยวิธี **Adaptive Grid Search**: เริ่มดึงแบบ centroid เดิมก่อน แล้วแตก grid เฉพาะตำบล/keyword ที่ผลลัพธ์ใกล้ชนเพดาน เพื่อเพิ่ม coverage โดยไม่ทำให้เวลารันพุ่งแบบ full grid ทั้งประเทศ

## Key Changes

- เพิ่ม preprocessing ให้สร้างไฟล์ admin3 polygon สำหรับ 10 จังหวัดเป้าหมาย เช่น `data/raw/target_admin3_search_units.geojson` โดยเก็บ polygon ระดับตำบล/แขวง พร้อม `province`, `district`, `admin3`, `admin3_pcode`, centroid
- เพิ่ม utility ใน `utils/geo_boundaries.py`:
  - โหลด admin3 polygon
  - สร้าง grid points ภายใน polygon
  - default grid spacing = `1.5 km`
  - จำกัดจำนวน grid ต่อ admin3 = `12 points`
  - env/config:
    - `GMAPS_SEARCH_MODE=adaptive`
    - `GMAPS_SATURATION_THRESHOLD=110`
    - `GMAPS_GRID_KM=1.5`
    - `GMAPS_MAX_GRID_POINTS_PER_ADMIN3=12`
- Refactor `scrape_gmaps_restaurants_by_geojson_areas()`:
  - Pass 1: ใช้ centroid เดิมทุก admin3 + 3 keywords
  - ถ้า search ใดได้ item `>= 110` ให้ mark ว่า saturated
  - Pass 2: เฉพาะ saturated admin3+keyword ให้แตก grid แล้ว search ซ้ำด้วย keyword เดิม
  - รวมผลทั้งหมดผ่าน dedup เดิม: พิกัดใกล้กัน `< 40m` และ cleaner dedup ชั้นสุดท้าย
- เพิ่ม log/report ต่อจังหวัด:
  - จำนวน centroid searches
  - จำนวน saturated searches
  - จำนวน adaptive grid searches
  - จำนวนร้านใหม่ก่อน/หลัง dedup

## Time Estimate With 2 Workers

ปัจจุบันมี `1,337` admin3 centroids และ `3` Google keywords:

```text
Base searches = 1,337 x 3 = 4,011 searches
```

เวลาปัจจุบันก่อน adaptive โดยประมาณ:

```text
4,011 searches / 2 workers
= 8-14 ชั่วโมง
```

หลังใช้ Adaptive Grid Search สมมติว่า search ที่ชนเพดานมีประมาณ `5-15%`:

```text
Saturated searches = 200-600
Extra grid searches = 200-600 x ~6 grid points average
                  = 1,200-3,600 extra searches

Total searches = 5,200-7,600
```

เวลารันใหม่โดยประมาณ:

```text
Adaptive, ไม่เปิด review filter: 12-22 ชั่วโมง
Adaptive, เปิด review filter: 18-32 ชั่วโมง
```

ถ้าใช้ Full Grid ทุกตำบลตั้งแต่แรก อาจพุ่งเป็น `40-80+ ชั่วโมง` ด้วย `2 workers` จึงไม่แนะนำเป็น default

## Test Plan

- รัน preprocessing แล้วตรวจว่าได้ `target_admin3_search_units.geojson` ครบ `1,337` admin3
- Unit check grid generation:
  - grid point ต้องอยู่ใน polygon
  - admin3 เล็กมากต้องมีอย่างน้อย 1 point
  - admin3 ใหญ่ต้องไม่เกิน cap `12 points`
- Dry run จังหวัดเล็ก เช่น `prachuap-khiri-khan`:
  - ดูจำนวน saturated searches
  - ดูจำนวน adaptive grid searches
  - เช็กว่า CSV ยังมี schema เดิมครบ
- Regression:
  - `py_compile` ไฟล์ที่แก้
  - รัน `run_restaurants_only.py` แบบเลือกจังหวัดเดียว และเช็ก output `restaurants_{slug}_clean.csv`

## Assumptions

- ใช้ Adaptive เป็น default
- threshold ชนเพดานใช้ `110` ไม่รอให้ถึง 120 เต็ม เพื่อกันกรณี Google truncate ก่อน
- grid spacing เริ่มต้น `1.5 km`
- จำกัด grid ต่อ admin3 ที่ `12 points` เพื่อคุมเวลารัน
- ยังใช้ dedup เดิมเป็นตัวกันร้านซ้ำจาก search grid ที่ overlap กัน
