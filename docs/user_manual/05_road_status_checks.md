# การตรวจผลข้อมูลถนน

## 1. ข้อมูลถนนไม่มีชื่อ

ถนนที่ไม่มีชื่อจาก OSM จะอยู่ในรูป:

```text
unnamed:<osm_id>
```

อย่าทับ `road_name` โดยตรง เพราะใช้ trace กลับ OSM ได้ ให้ใช้ `road_display_name` สำหรับ dashboard/report แทน

## 2. สถานะที่พบบ่อย

- `matched`: เติมชื่อจาก Google ได้
- `no_route`: Google ไม่คืนชื่อถนนที่ใช้ได้
- `skipped_has_ref`: ไม่มีชื่อ แต่มี `road_ref` จึง fallback เป็น `Road <ref>`
- `skipped_named`: มีชื่อจาก OSM อยู่แล้ว

## 3. วิธีเช็กผลเร็ว ๆ

ดูจำนวนแถวแยกตามสถานะ:

```powershell
Import-Csv data\processed\roads_final.csv |
  Group-Object google_match_status |
  Select-Object Name,Count
```

ดูตัวอย่างชื่อถนน:

```powershell
Import-Csv data\processed\roads_final.csv |
  Select-Object -First 20 province,road_name,road_display_name
```

ดูเฉพาะแถวที่ยังไม่มีชื่อถนนที่ใช้ได้:

```powershell
Import-Csv data\processed\roads_final.csv |
  Where-Object { $_.google_match_status -eq "no_route" } |
  Select-Object province,osm_id,highway_type,road_display_name
```

## 4. ไฟล์ที่ควรใช้ต่อ

สำหรับงานทั่วไปให้ใช้:

```text
data/processed/roads_final.csv
```

ถ้าต้อง audit ว่า Google คืนอะไรมา ให้เปิด:

```text
data/processed/roads_enriched.csv
```
