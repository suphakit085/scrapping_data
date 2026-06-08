# Troubleshooting หลัก

## 1. Google API ขึ้น `REQUEST_DENIED`

ให้ตรวจ 3 จุดนี้:

- เปิด Billing ใน Google Cloud Project แล้วหรือยัง
- เปิด `Geocoding API` แล้วหรือยัง
- API key restriction ตรงกับการใช้งานหรือไม่

สำหรับ script Python ควรใช้:

- Application restriction: `IP addresses` ถ้าเครื่องมี public IP คงที่
- API restriction: จำกัดเฉพาะ `Geocoding API`

ถ้ารันจากเน็ตบ้านที่ IP เปลี่ยนบ่อย ให้ตั้ง quota ต่ำ ๆ ระหว่างทดสอบ เช่น 200-500 requests/day

## 2. Playwright เปิด browser ไม่ได้

บาง scraper ใช้ Playwright ถ้า browser binary หาย ให้รัน:

```powershell
python -m playwright install chromium
```

ถ้า network ถูกจำกัด อาจต้องรันใน environment ที่ดาวน์โหลด browser ได้

## 3. Pipeline หยุดเพราะ Quality Gate

ทั้ง `main.py` และ `run_zones_only.py` มีการตรวจ output ก่อนถือว่าสำเร็จ ถ้า fail ให้ดูข้อความ error แล้วตรวจไฟล์เหล่านี้:

```text
data/processed/landmarks_clean.csv
data/processed/zone_profiles.csv
```

ถ้าไฟล์ใดหาย ให้ย้อนกลับไปรัน pipeline ที่สร้างไฟล์นั้นก่อน

## 4. เมื่อ output หายหรือแถวไม่ครบ

ให้ตรวจจำนวนแถวจากไฟล์ต้นทางและไฟล์ปลายทางก่อนเสมอ:

```powershell
(Import-Csv data\processed\roads.csv | Measure-Object).Count
(Import-Csv data\processed\roads_final.csv | Measure-Object).Count
```

ถ้า `roads_enriched.csv` ถูกเขียนไม่ครบ ให้ regenerate จาก cache โดยไม่ยิง API เพิ่ม:

```powershell
python run_google_road_enrichment.py --limit 0 --sleep-seconds 0
```

จากนั้นค่อย export `roads_final.csv` ใหม่
