# คู่มือผู้ใช้โปรเจกต์ `ai_web_scrpping`

## 1. โปรเจกต์นี้ใช้ทำอะไร

`ai_web_scrpping` เป็น data pipeline สำหรับรวบรวมข้อมูลเชิงพื้นที่ของ 10 จังหวัดในไทย โดยเน้น landmark, POI, amenity และถนน แล้วแปลงเป็นไฟล์ CSV/JSON ที่นำไปใช้ต่อในงานวิเคราะห์, dashboard, BI หรือรายงานพื้นที่ได้ทันที

ข้อมูลหลักที่ระบบจัดการมี 4 กลุ่ม:

- จุดสำคัญและสิ่งอำนวยความสะดวก เช่น landmark, restaurant, amenity
- ถนนและโครงข่ายถนนจาก OpenStreetMap และ Google road enrichment
- ข้อมูลบริบทพื้นที่ เช่น ประชากร อากาศ น้ำท่วม และ zone profile
- ชุดข้อมูลถนนปลายทางสำหรับใช้ร่วมกับ landmark เช่น `roads_final.csv`

## 2. สิ่งที่ต้องเตรียมก่อนรัน

ให้รันทุกคำสั่งจาก root ของโปรเจกต์:

```powershell
cd C:\ai_web_scrpping
.\venv\Scripts\Activate.ps1
```

ตรวจไฟล์ `.env` ว่ามี key ที่จำเป็น:

```env
BOT_API_KEY=...
GOOGLE_MAPS_API_KEY=...
```

หมายเหตุ:

- `BOT_API_KEY` ใช้กับข้อมูลสินเชื่อจาก Bank of Thailand
- `GOOGLE_MAPS_API_KEY` ใช้กับ Google road-name enrichment
- ห้าม commit `.env` เพราะมี secret

## 3. โครงสร้างไฟล์ที่ควรรู้

```text
data/raw/        ข้อมูลดิบและ cache จาก scraper
data/processed/  ไฟล์ CSV ที่พร้อมนำไปใช้ต่อ
scrapers/        ตัวดึงข้อมูลจากแหล่งต่าง ๆ
utils/           ตัว clean, merge, analyze, validate
tests/           unit tests ของ pipeline
```

## 4. กฎสำคัญเวลาใช้งาน

- อย่ารันไฟล์ scraper ใน `scrapers/` ตรง ๆ เพราะบางไฟล์ใช้ relative path ที่อาจผิดจาก repo root
- ใช้ entrypoint ที่ root เช่น `python main.py`, `python run_roads_only.py`
- ก่อนลบไฟล์ใน `data/raw/` ให้เช็กก่อน เพราะหลายไฟล์เป็น cache ช่วยประหยัดเวลาและ API quota
- ไฟล์ CSV ใน `data/processed/` เป็น output ใช้งานจริง แต่ส่วนใหญ่ถูก ignore ใน git
