# User Manual: AI Web Scraping & Location Intelligence Pipeline

คู่มือการใช้งานระบบ Data Pipeline สำหรับวิเคราะห์ข้อมูลพื้นที่ (Location Intelligence) โปรเจกต์นี้มีเป้าหมายเพื่อดึงข้อมูลจากหลายแหล่ง (OSM, Google Maps, ทศท., ฯลฯ) แล้วนำมาประมวลผลเป็นชุดข้อมูลพร้อมใช้งาน

---

## 1. การเตรียมความพร้อมก่อนใช้งาน (Prerequisites & Setup)

ก่อนที่จะเริ่มรันคำสั่งใดๆ ให้ตรวจสอบว่าระบบของคุณตั้งค่าครบถ้วนแล้ว:

1. **Python Environment**:
   - โปรเจกต์นี้ทำงานบน **Python 3.13** 
   - ควรใช้ Virtual Environment (`venv/`) ที่มีอยู่ในโปรเจกต์
2. **การติดตั้ง Playwright** (สำคัญมากสำหรับการดึงข้อมูลจากเว็บและ Google Maps):
   - หากยังไม่มี Browser binaries ให้รันคำสั่ง:
     ```bash
     python -m playwright install chromium
     ```
3. **Environment Variables**:
   - สร้างหรือตรวจสอบไฟล์ `.env` ที่ root ของโปรเจกต์
   - จำเป็นต้องมี `BOT_API_KEY` สำหรับการดึงข้อมูลสินเชื่อธนาคาร มิเช่นนั้น output ของ bank loans จะว่างเปล่า
4. **S3 Upload (ถ้าใช้งาน)**:
   - ใน `main.py` มีการกำหนด placeholder bucket name (`your-target-bucket-name`) หากต้องการให้ทำงานสมบูรณ์ ต้องอัปเดตชื่อ Bucket และตั้งค่า AWS Credentials ในเครื่องให้เรียบร้อย

---

## 2. วิธีการใช้งานสคริปต์หลัก (Entry Points)

โปรเจกต์นี้ถูกออกแบบให้เรียกใช้งานจาก **Root Directory** เสมอ (ห้าม cd เข้าไปรันสคริปต์ในโฟลเดอร์ย่อย เช่น `scrapers/` เพราะจะทำให้ relative path ของไฟล์ data พัง)

### 2.1 รัน Pipeline เต็มรูปแบบ (`main.py`)
คำสั่งนี้จะรันการทำงานครอบคลุมตั้งแต่ต้นจนจบ เหมาะสำหรับการอัปเดตข้อมูลทั้งหมดในรอบเดียว
```bash
python main.py
```
**ลำดับการทำงาน:**
1. ดึงข้อมูลอัตราดอกเบี้ยสินเชื่อ (Bank loans)
2. ดึงข้อมูลจุดสังเกตและสถานที่สำคัญ (Landmarks จาก OSM)
3. เติมเต็มข้อมูลสถานที่ด้วย Google Maps (Enrich)
4. ทำความสะอาดและรวมไฟล์ (Clean & Merge CSVs)
5. อัปโหลดผลลัพธ์ขึ้น S3

### 2.2 รันแยกตามประเภทข้อมูลย่อย (Modular Scripts)
คุณสามารถรันเฉพาะสคริปต์ย่อยที่สนใจได้ตามต้องการ ตัวอย่างเช่น:
- `python run_landmarks_only.py` : ดึงเฉพาะข้อมูล Landmark
- `python run_roads_only.py` : วิเคราะห์และดึงโครงข่ายถนน
- `python run_amenities_only.py` : ดึงเฉพาะสิ่งอำนวยความสะดวก
- `python run_restaurants_only.py` : ดึงข้อมูลร้านอาหาร
- `python run_property_road_access.py` : ประมวลผลและหาระยะเชื่อมต่อของอสังหาฯ ออกสู่ถนนสายหลัก
- `python run_google_road_enrichment.py` : ใช้ Google ช่วยตรวจสอบถนนที่เข้าถึงยาก

---

## 3. ฟังก์ชันและการทำงานหลักที่สำคัญ (Core Features)

### 3.1 Landmarks & POI Extraction (การค้นหาสถานที่สำคัญ)
- **แหล่งข้อมูล**: เริ่มต้นดึงจาก OpenStreetMap (ผ่าน Overpass API) ในฟังก์ชันของ `scrapers/landmarks.py`
- **Enrichment**: เพื่อให้ข้อมูลแม่นยำขึ้น `scrapers/google_maps_sync.py` จะโหลดไฟล์ `landmarks_raw.json` แล้วใช้ Playwright เข้าค้นหาบน Google Maps อัตโนมัติ เพื่อดึงพิกัดที่แท้จริง รีวิว และหมวดหมู่เพิ่มเติม 
- **Layer System**: สถานที่จะถูกแบ่งเป็นระดับ เช่น Layer 1 (Anchor สำคัญระดับภูมิภาค/จังหวัด), Layer 2 (สถานที่ระดับท้องถิ่น)
- *คำแนะนำ*: ระบบจะดึง Layer 2 เฉพาะจังหวัดเป้าหมายจากไฟล์ `data/raw/local_iconic_targets.json` 

### 3.2 Road Access & Routing (การเข้าถึงถนนหลัก)
- ทำงานผ่านสคริปต์เช่น `run_property_road_access.py` และ `utils/property_road_access.py`
- **หน้าที่**: คำนวณหาระยะที่ใกล้ที่สุดจากพิกัดอสังหาริมทรัพย์ ออกไปยังซอย (Local Road) และหาเส้นทางสั้นที่สุดไปสู่ถนนสายหลัก (Major Road: motorway, trunk, primary ฯลฯ) 

---

## 4. โครงสร้างข้อมูลที่ได้ (Data Outputs)

โฟลเดอร์หลักที่สำคัญสำหรับการเอาข้อมูลไปใช้ต่อมีดังนี้:

- **`data/raw/`**: เก็บข้อมูลดิบ (JSON) หรือข้อมูลตั้งต้น เช่น ข้อมูลจากการ Scrape โดยตรงที่ยังไม่ผ่านการลบข้อมูลซ้ำซ้อน ไม่แนะนำให้นำไปใช้วิเคราะห์ตรงๆ
- **`data/processed/`**: เป็น **Canonical Outputs** หรือข้อมูลที่ทำความสะอาดเรียบร้อยแล้ว แนะนำให้ใช้ข้อมูลจากโฟลเดอร์นี้เสมอ
  - `landmarks_clean.csv` : ข้อมูลสถานที่สำคัญที่ลบตัวซ้ำและปรับ Format แล้ว
  - `bank_loans_clean.csv` : อัตราดอกเบี้ยและข้อมูลสินเชื่อ
  - `roads_final.csv` : สรุปข้อมูลโครงข่ายถนน

---

## 5. ข้อควรระวังและการแก้ไขปัญหา (Troubleshooting & Gotchas)

1. **อย่ารัน Scraper ตรงๆ จากโฟลเดอร์ `scrapers/`**
   - เช่น การรัน `python scrapers/landmarks.py` มักจะเกิด Error หาไฟล์ไม่เจอ เนื่องจากภายในโค้ดอ้างอิง path เริ่มต้นจาก root (เช่น `../data/`) ให้ใช้สคริปต์ที่มีคำว่า `run_` นำหน้าบนโฟลเดอร์ root เสมอ
2. **Browser (Playwright) ขัดข้อง**
   - หากรันแล้วเจอ Error เกี่ยวกับ Browser ให้ลองเช็คว่าติดตั้ง Chromium หรือยัง (`python -m playwright install chromium`)
   - ในบางครั้ง Google Maps อาจโหลดช้าและติด Timeout ให้พิจารณาจำนวน Thread หรือปรับรอเวลา
3. **ไฟล์ `__pycache__` รกใน Git**
   - ใน repo ยังไม่มี `.gitignore` ในส่วน root แบบสมบูรณ์ อาจจะมี `__pycache__` โผล่มา ไม่ต้องตกใจ (สามารถลบทิ้งได้ถ้าต้องการคลีน)
4. **S3 Upload Failed**
   - หากรัน `main.py` ไปถึงขั้นสุดท้ายแล้วมี Error ให้เช็ค AWS Configuration ของเครื่องคุณ และแก้ชื่อ Bucket ในโค้ด
5. **แก้โค้ดแล้วผลลัพธ์ไม่เปลี่ยน (Cache Issue)**
   - ระบบมักจะมีการเซฟสถานะใน `data/raw/` ถ้าคุณเปลี่ยน Logic แต่อยากดึงใหม่ทั้งหมด อาจจะต้องสำรองหรือลบไฟล์ raw ที่เกี่ยวข้องทิ้ง (เช่น `landmarks_raw.json` หรือ `geocode_cache.json`) เพื่อให้ดึงข้อมูลใหม่

---
*จัดทำขึ้นเพื่อให้ทีมนักพัฒนาและวิเคราะห์ข้อมูลทำงานร่วมกันบนสถาปัตยกรรมเดียวกัน*
