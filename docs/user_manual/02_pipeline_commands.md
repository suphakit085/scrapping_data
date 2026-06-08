# คำสั่งรัน Pipeline หลัก

## 1. Full Pipeline

ใช้เมื่ออยากรันกระบวนการหลักทั้งหมด:

```powershell
python main.py
```

เมื่อรันแล้วจะเจอเมนูหลัก:

```text
[1] รันทุกอย่าง (Full Pipeline)
[2] ดึงเฉพาะ Landmarks (OSM + Google Maps Sync)
[3] ดึงเฉพาะ Restaurants
[4] เลือกเองทีละรายการ (Custom)
[q] ออกจากโปรแกรม
```

วิธีเลือก:

- กด `1` ถ้าต้องการรัน pipeline หลักแบบครบชุด
- กด `2` ถ้าต้องการอัปเดตเฉพาะ landmark/POI จาก OSM และ Google Maps
- กด `3` ถ้าต้องการดึงเฉพาะร้านอาหาร
- กด `4` ถ้าต้องการเลือก module เอง เช่น เลือกเฉพาะ bank loans, landmarks หรือ Google Maps sync
- กด `q` เพื่อออกจากโปรแกรม

ลำดับโดยรวม:

1. ดึงข้อมูลสินเชื่อธนาคาร
2. ดึง landmarks และ POI
3. sync Google Maps เพื่อเติมข้อมูลสถานที่
4. clean/merge CSV
5. วิเคราะห์ zones จาก landmark และข้อมูลบริบทพื้นที่
6. ตรวจ quality gate
7. upload ไป S3

ข้อควรระวัง: ใน `main.py` ยังมี bucket placeholder `your-target-bucket-name` ถ้ายังไม่ได้ตั้ง S3 จริง อาจไม่ควรใช้ flow upload เป็นงาน production

## 2. Zone Pipeline

ใช้เมื่อต้องการสร้าง micro-zone intelligence:

```powershell
python run_zones_only.py
```

ไฟล์นี้เหมาะกับงานที่ต้องการดูภาพพื้นที่จาก landmark, road network, population, weather และ flood context เป็นหลัก
