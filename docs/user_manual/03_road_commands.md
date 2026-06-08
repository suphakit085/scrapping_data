# Road Dataset และ Google Enrichment

## 1. Road Dataset

ดึงข้อมูลถนนจาก OpenStreetMap:

```powershell
python run_roads_only.py
```

ผลลัพธ์หลัก:

```text
data/raw/roads_raw.json
data/raw/roads_raw_quality_report.json
data/processed/roads.csv
```

สร้าง road intelligence แยกได้ด้วยคำสั่งนี้:

```powershell
python run_road_intelligence.py
```

ได้ไฟล์ `roads_features.csv`, `roads_summary_by_province.csv`, `road_density_by_zone.csv`, `road_intersections.csv`

## 2. Google Road Name Enrichment

เติมชื่อถนนให้แถว `unnamed:*` ที่ไม่มี `road_ref`:

```powershell
python run_google_road_enrichment.py --sleep-seconds 0.1 --cache-flush-interval 25
```

ทดสอบโดยไม่ยิง Google API:

```powershell
python run_google_road_enrichment.py --dry-run --limit 20
```

สร้าง output จาก cache เดิมโดยไม่ยิง API เพิ่ม:

```powershell
python run_google_road_enrichment.py --limit 0 --sleep-seconds 0
```

ไฟล์ปลายทางที่แนะนำให้ใช้ต่อคือ:

```text
data/processed/roads_final.csv
```
