import json
import os
import re

from shapely.geometry import Point, shape
from shapely.prepared import prep
from shapely.strtree import STRtree


TARGET_BOUNDARY_PATH = "data/raw/target_admin_boundaries.geojson"
TARGET_ADMIN3_CENTROIDS_PATH = "data/raw/target_admin3_centroids.json"


PROVINCE_SLUG_TO_ADM1 = {
    "khon-kaen": "Khon Kaen",
    "ubon-ratchathani": "Ubon Ratchathani",
    "prachuap-khiri-khan": "Prachuap Khiri Khan",
    "udon-thani": "Udon Thani",
    "rayong": "Rayong",
    "chonburi": "Chon Buri",
    "surin": "Surin",
    "buriram": "Buri Ram",
    "phitsanulok": "Phitsanulok",
    "chiang-rai": "Chiang Rai",
}

TARGET_PROVINCES = set(PROVINCE_SLUG_TO_ADM1.values())

PROVINCE_ALIASES = {
    "chonburi": "Chon Buri",
    "chon buri": "Chon Buri",
    "buriram": "Buri Ram",
    "buri ram": "Buri Ram",
    "prachuapkhirikhan": "Prachuap Khiri Khan",
    "prachuap khiri khan": "Prachuap Khiri Khan",
}


def repo_path(relative_path: str) -> str:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo_root, relative_path)


def normalize_province_name(name):
    if not name:
        return ""

    cleaned = str(name).strip()
    key = re.sub(r"[^a-z0-9]+", " ", cleaned.lower()).strip()
    compact_key = key.replace(" ", "")

    if key in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[key]
    if compact_key in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[compact_key]

    for canonical in TARGET_PROVINCES:
        canonical_key = re.sub(r"[^a-z0-9]+", " ", canonical.lower()).strip()
        if key == canonical_key or compact_key == canonical_key.replace(" ", ""):
            return canonical

    return cleaned


def province_slug_to_adm1(slug):
    return normalize_province_name(PROVINCE_SLUG_TO_ADM1.get(slug, slug))


def is_in_thailand_bounds(lat, lon):
    return (5.0 <= lat <= 20.5) and (97.0 <= lon <= 106.0)


def load_target_boundaries(boundary_path=TARGET_BOUNDARY_PATH):
    abs_path = repo_path(boundary_path)
    if not os.path.exists(abs_path):
        print(f"  [WARN] Target boundary file not found: {abs_path}")
        print("  [WARN] Run: python utils/preprocess_target_boundaries.py")
        print("  [WARN] Falling back to Thailand bounding-box filtering only.")
        return {}

    with open(abs_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    boundaries = {}
    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        province = normalize_province_name(
            props.get("adm1_name_normalized") or props.get("adm1_name")
        )
        if not province:
            continue

        try:
            boundaries.setdefault(province, []).append(prep(shape(feature["geometry"])))
        except Exception as e:
            print(f"  [WARN] Skipping invalid boundary for {province}: {e}")

    print(
        f"  [OK] Loaded province boundaries: "
        f"{len(boundaries)} provinces, {sum(len(v) for v in boundaries.values())} polygons"
    )
    return boundaries


def point_in_province(lat, lon, province_en, province_boundaries):
    if not is_in_thailand_bounds(lat, lon):
        return False

    province_key = normalize_province_name(province_en)
    province_geoms = province_boundaries.get(province_key)
    if not province_geoms:
        return True

    point = Point(lon, lat)
    return any(geom.contains(point) or geom.intersects(point) for geom in province_geoms)


def load_admin3_centroids(centroids_path=TARGET_ADMIN3_CENTROIDS_PATH):
    abs_path = repo_path(centroids_path)
    if not os.path.exists(abs_path):
        print(f"  [WARN] Admin3 centroid file not found: {abs_path}")
        print("  [WARN] Run: python utils/preprocess_target_boundaries.py")
        return {}

    with open(abs_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    by_province = {}
    for record in records:
        province = normalize_province_name(record.get("province"))
        if not province:
            continue
        by_province.setdefault(province, []).append(record)

    return by_province


def build_spatial_index(target_provinces=TARGET_PROVINCES):
    print("  -> Loading full admin boundaries for Reverse Geocoding (This may take 10-15 seconds)...")
    boundary_path = repo_path("data/the_admin_boundaries.geojson")
    
    if not os.path.exists(boundary_path):
        print(f"  [WARN] {boundary_path} not found! Reverse Geocoding will return empty strings.")
        return None, [], []
        
    with open(boundary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    polygons = []
    properties = []
    
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        prov = normalize_province_name(props.get("adm1_name1") or props.get("adm1_name"))
        if prov in target_provinces:
            try:
                geom = shape(feature["geometry"])
                polygons.append(geom)
                properties.append({
                    "district": props.get("adm2_name1", ""),
                    "sub_district": props.get("adm3_name1", "")
                })
            except Exception:
                continue
                
    print(f"  -> Building spatial index for {len(polygons)} tambons...")
    tree = STRtree(polygons)
    return tree, polygons, properties


def reverse_geocode(lat, lon, tree, polygons, properties):
    if not tree or lat is None or lon is None:
        return "", ""
    point = Point(lon, lat)
    matches = tree.query(point)
    for idx in matches:
        if polygons[idx].contains(point) or polygons[idx].intersects(point):
            return properties[idx]["district"], properties[idx]["sub_district"]
    return "", ""


def prompt_admin_areas(scraper_name):
    print(f"\n⚙️  [Terminal UI - {scraper_name}]")
    print("❓ คุณต้องการดึงข้อมูล อำเภอ (District) และ ตำบล (Sub-district) ด้วยหรือไม่?")
    print("   👉 [y] ยอมรับ (ใช้เวลาโหลด GeoJSON เพิ่มประมาณ 10-15 วินาที)")
    print("   👉 [n] ข้าม (ไม่ดึงข้อมูลในระดับพื้นที่ย่อยเพื่อประหยัด RAM/เวลา)")
    print("   👉 [q] ออกจากโปรแกรม")
    while True:
        choice = input("กรุณาเลือก (y/n/q): ").strip().lower()
        if choice in ('y', 'yes'):
            return True
        elif choice in ('n', 'no'):
            return False
        elif choice in ('q', 'quit', 'exit'):
            print("\n👋 ออกจากโปรแกรมแล้ว")
            raise SystemExit(0)
        print("❌ เลือกไม่ถูกต้อง กรุณาพิมพ์ y, n หรือ q")


# ============================================================
# Freshness Filter — Date Utilities
# ============================================================

BUDDHIST_ERA_OFFSET = 543


def ce_to_be(ce_year: int) -> int:
    """ค.ศ. → พ.ศ."""
    return ce_year + BUDDHIST_ERA_OFFSET


def be_to_ce(be_year: int) -> int:
    """พ.ศ. → ค.ศ."""
    return be_year - BUDDHIST_ERA_OFFSET


def parse_osm_timestamp_year(timestamp: str):
    """แปลง OSM ISO timestamp → ปี ค.ศ.
    Input:  '2021-06-15T10:23:00Z'
    Output: 2021
    """
    try:
        return int(str(timestamp)[:4])
    except Exception:
        return None


def parse_review_relative_year(relative_text: str):
    """แปลง relative review text → ปี ค.ศ.
    Input:  '2 ปีที่แล้ว' / '3 years ago' / 'a month ago'
    Output: ปี ค.ศ. (int) หรือ None
    """
    from datetime import datetime
    current_year = datetime.now().year
    text = (relative_text or "").lower().strip()

    # ปีที่แล้ว / years ago
    m = re.search(r'(\d+)\s*(year|ปี)', text)
    if m:
        return current_year - int(m.group(1))

    # เดือน / สัปดาห์ / วัน / ชั่วโมง → ปีปัจจุบัน
    if re.search(r'month|week|day|hour|เดือน|สัปดาห์|วัน|ชั่วโมง|นาที|minute|second|วินาที', text):
        return current_year

    # "a year ago"
    if re.search(r'a year|หนึ่งปี|1 ปี', text):
        return current_year - 1

    return None


# ============================================================
# Freshness Filter — Terminal UI Prompts
# ============================================================

def _prompt_year_threshold(prompt_label: str):
    """Helper: ถามปี พ.ศ. ขั้นต่ำ คืนค่าเป็น ค.ศ. หรือ None ถ้าไม่กรอก"""
    while True:
        raw = input(prompt_label).strip()
        if not raw:
            return None
        if raw.lower() in ('q', 'quit', 'exit'):
            print("\n👋 ออกจากโปรแกรมแล้ว")
            raise SystemExit(0)
        try:
            be = int(raw)
            if be > 2400:          # เป็น พ.ศ. แน่นอน
                return be_to_ce(be)
            elif be > 1900:        # เป็น ค.ศ. แน่นอน
                return be
            else:
                print("   ⚠️  ปีที่กรอกดูผิดปกติ จะใช้เป็น พ.ศ. โดยอัตโนมัติ")
                return be_to_ce(be)
        except ValueError:
            print("   ❌ กรุณากรอกเป็นตัวเลขปี พ.ศ./ค.ศ. หรือกด [Enter] เพื่อดึงทั้งหมด (หรือ q เพื่อออก)")


def prompt_gmaps_review_filter():
    """ถามผู้ใช้ว่าต้องการกรองโดยวันที่ Review ล่าสุดจาก Google Maps ไหม
    คืนค่า: (enable: bool, min_ce_year: int | None)
    """
    print("\n⚙️  [Terminal UI - Google Maps Review Freshness Filter]")
    print("❓ ต้องการกรองร้านที่ไม่มีรีวิวใหม่หรือไม่?")
    print("   👉 [y] กำหนดปี พ.ศ. ขั้นต่ำของรีวิวล่าสุด")
    print("   👉 [n] ไม่กรอง (ดึงทั้งหมด)")
    print("   👉 [q] ออกจากโปรแกรม")
    while True:
        choice = input("กรุณาเลือก (y/n/q): ").strip().lower()
        if choice in ('y', 'yes'):
            min_ce = _prompt_year_threshold(
                "   กรอกปี พ.ศ. ขั้นต่ำ เช่น 2567 (Enter = ทั้งหมด): "
            )
            be_display = ce_to_be(min_ce) if min_ce else "—"
            print(f"   ✅ จะดึงเฉพาะร้านที่มีรีวิวตั้งแต่ พ.ศ. {be_display} ขึ้นไป")
            return True, min_ce
        elif choice in ('n', 'no'):
            return False, None
        elif choice in ('q', 'quit', 'exit'):
            print("\n👋 ออกจากโปรแกรมแล้ว")
            raise SystemExit(0)
        print("❌ เลือกไม่ถูกต้อง กรุณาพิมพ์ y, n หรือ q")


def prompt_osm_last_edit_filter():
    """ถามผู้ใช้ว่าต้องการกรองโดย OSM timestamp (วันแก้ไขล่าสุด) ไหม
    คืนค่า: (enable: bool, min_ce_year: int | None)
    """
    print("\n⚙️  [Terminal UI - OSM Last Edit Filter]")
    print("❓ ต้องการกรอง OSM POI ที่ไม่มีการอัปเดตหรือไม่?")
    print("   👉 [y] กำหนดปี พ.ศ. ขั้นต่ำของการแก้ไขล่าสุด")
    print("   👉 [n] ไม่กรอง (ดึงทั้งหมด)")
    print("   👉 [q] ออกจากโปรแกรม")
    while True:
        choice = input("กรุณาเลือก (y/n/q): ").strip().lower()
        if choice in ('y', 'yes'):
            min_ce = _prompt_year_threshold(
                "   กรอกปี พ.ศ. ขั้นต่ำ เช่น 2564 (Enter = ทั้งหมด): "
            )
            be_display = ce_to_be(min_ce) if min_ce else "—"
            print(f"   ✅ จะดึงเฉพาะ OSM POI ที่แก้ไขล่าสุดตั้งแต่ พ.ศ. {be_display} ขึ้นไป")
            return True, min_ce
        elif choice in ('n', 'no'):
            return False, None
        elif choice in ('q', 'quit', 'exit'):
            print("\n👋 ออกจากโปรแกรมแล้ว")
            raise SystemExit(0)
        print("❌ เลือกไม่ถูกต้อง กรุณาพิมพ์ y, n หรือ q")


def prompt_osm_created_filter():
    """ถามผู้ใช้ว่าต้องการกรองโดยปีที่สร้าง OSM (ใช้ version=1 + timestamp เป็น proxy) ไหม
    คืนค่า: (enable: bool, min_ce_year: int | None)
    """
    print("\n⚙️  [Terminal UI - OSM Created Year Filter]")
    print("❓ ต้องการดึงเฉพาะ OSM POI ที่สร้างตั้งแต่ปีที่กำหนดหรือไม่?")
    print("   (ใช้ version=1 + timestamp เป็น proxy ของวันที่สร้าง)")
    print("   👉 กรอกปี พ.ศ. เริ่มต้น เช่น 2565")
    print("   👉 กด Enter เพื่อดึงทั้งหมด (ไม่กรอง)")
    print("   👉 [q] ออกจากโปรแกรม")
    while True:
        raw = input("   ปี พ.ศ. เริ่มต้น (Enter = ทั้งหมด หรือ q เพื่อออก): ").strip()
        if raw.lower() in ('q', 'quit', 'exit'):
            print("\n👋 ออกจากโปรแกรมแล้ว")
            raise SystemExit(0)
        if not raw:
            return False, None
        try:
            be = int(raw)
            min_ce = be_to_ce(be) if be > 2400 else be
            be_display = ce_to_be(min_ce)
            print(f"   ✅ จะดึงเฉพาะ OSM POI ที่สร้างตั้งแต่ พ.ศ. {be_display} ขึ้นไป")
            return True, min_ce
        except ValueError:
            print("   ❌ กรุณากรอกเป็นตัวเลขปี พ.ศ./ค.ศ. หรือกด [Enter] เพื่อดึงทั้งหมด (หรือ q เพื่อออก)")


def prompt_parallel_workers(label: str, default_workers: int = 4, max_recommended: int = 8) -> int:
    """ถามผู้ใช้ใน Terminal ณ จุดเริ่มต้น เพื่อกำหนดจำนวนคนทำงานขนานในหัวข้อนั้นๆ"""
    print(f"\n⚙️  [Terminal UI - {label} Parallel Settings]")
    print(f"❓ ต้องการระบุจำนวนคนทำงานขนาน (Parallel Workers) หรือไม่?")
    print(f"   👉 กรอกตัวเลขระหว่าง 1 ถึง {max_recommended} (แนะนำ: {default_workers})")
    print(f"   👉 กด [Enter] เพื่อใช้ค่าเริ่มต้น ({default_workers})")
    print(f"   👉 [q] ออกจากโปรแกรม")
    while True:
        raw = input(f"   จำนวนคนทำงาน (1-{max_recommended}, Default={default_workers}, หรือ q): ").strip().lower()
        if raw in ('q', 'quit', 'exit'):
            print("\n👋 ออกจากโปรแกรมแล้ว")
            raise SystemExit(0)
        if not raw:
            return default_workers
        try:
            val = int(raw)
            if 1 <= val <= 32:
                return val
            print("❌ จำนวนไม่อยู่ในช่วงที่กำหนด กรุณาลองใหม่")
        except ValueError:
            print("❌ กรุณากรอกจำนวนเป็นตัวเลข หรือพิมพ์ q เพื่อออก")


def prompt_resume_or_fresh(label: str, temp_dir: str) -> bool:
    """
    ตรวจสอบไฟล์ชั่วคราวเก่า และถามผู้ใช้ว่าต้องการรันต่อ (Resume) หรือเริ่มใหม่แบบปลอดภัย (Start Fresh)
    - คืนค่า True: รันต่อ (Resume)
    - คืนค่า False: เริ่มใหม่ (Start Fresh - ซึ่งย้ายไฟล์เก่าไปสำรองแล้ว)
    """
    import glob
    import shutil
    import time
    
    if not os.path.exists(temp_dir):
        return True
        
    temp_files = glob.glob(os.path.join(temp_dir, "*.json"))
    if not temp_files:
        return True

    # สร้างชื่อโฟลเดอร์สำรองข้อมูลตามเวลาปัจจุบัน
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = f"{temp_dir.rstrip('/\\\\')}_backup_{timestamp}"

    print(f"\n⚙️  [Terminal UI - {label} Resume Check]")
    print(f"⚠️  พบข้อมูลชั่วคราวจากการรันครั้งก่อนหน้า ({len(temp_files)} จังหวัด) ในโฟลเดอร์:")
    print(f"   📂 {os.path.abspath(temp_dir)}")
    print("❓ คุณต้องการทำงานอย่างไร?")
    print("   👉 [r] ทำงานต่อจากของเดิม (Resume Mode)")
    print(f"   👉 [f] เริ่มใหม่ทั้งหมดอย่างปลอดภัย (Start Fresh - สำรองไฟล์เก่าไปที่ {os.path.basename(backup_dir)})")
    print("   👉 [q] ออกจากโปรแกรม")
    
    while True:
        mode_choice = input("กรุณาเลือก (r/f/q): ").strip().lower()
        if mode_choice in ('q', 'quit', 'exit'):
            print("\n👋 ออกจากโปรแกรมแล้ว")
            raise SystemExit(0)
            
        elif mode_choice in ('f', 'fresh', 'startfresh'):
            print(f"   📦 กำลังย้ายข้อมูลเก่าไปสำรองที่ {os.path.basename(backup_dir)}...")
            try:
                shutil.move(temp_dir, backup_dir)
                print("   ✅ สำรองข้อมูลและเตรียมเริ่มต้นรันใหม่เสร็จสิ้น")
            except Exception as e:
                print(f"   ⚠️  ไม่สามารถย้ายโฟลเดอร์ชั่วคราวทั้งหมดได้: {e}")
            return False
            
        elif mode_choice in ('r', 'resume'):
            print("\n📋 รายการไฟล์ชั่วคราวรายจังหวัดที่ตรวจพบ:")
            # ดึงเฉพาะชื่อไฟล์และพยายามจับคู่กับชื่อจังหวัดในภาษาไทย
            file_options = []
            for idx, filepath in enumerate(sorted(temp_files), 1):
                filename = os.path.basename(filepath)
                # พยายามแยกแยะ slug จังหวัด
                slug_match = re.search(r'_(.+)\.json$', filename)
                slug_display = slug_match.group(1) if slug_match else filename
                file_options.append((idx, filepath, filename, slug_display))
                print(f"   [{idx}] {filename} ({slug_display})")
                
            print("\n❓ คุณต้องการรันต่อโดยข้าม (Skip) ไฟล์จังหวัดใดบ้าง?")
            print("   👉 พิมพ์หมายเลขไฟล์ติดกันเพื่อเลือก เช่น 13 (เลือกไฟล์ 1 และ 3 เพื่อใช้รันต่อ)")
            print("   👉 กด [Enter] เพื่อรันต่อจากทุกไฟล์ที่มีทั้งหมด (Resume All)")
            print("   👉 [q] ออกจากโปรแกรม")
            
            while True:
                select_choice = input("กรุณาเลือก (หมายเลขไฟล์, Enter = ใช้ทั้งหมด, หรือ q): ").strip().lower()
                if select_choice in ('q', 'quit', 'exit'):
                    print("\n👋 ออกจากโปรแกรมแล้ว")
                    raise SystemExit(0)
                
                # เคส 1: กด Enter คือ ใช้ไฟล์ทั้งหมดรันต่อ
                if not select_choice:
                    print("   ✅ ยอมรับไฟล์เดิมทั้งหมดเพื่อรันงานต่อ")
                    return True
                    
                # เคส 2: เลือกเฉพาะบางไฟล์
                if select_choice.isdigit():
                    selected_indices = [int(char) for char in select_choice]
                    # ตรวจความถูกต้องของหมายเลข
                    if all(1 <= i <= len(file_options) for i in selected_indices):
                        # สร้างโฟลเดอร์สำรอง
                        os.makedirs(backup_dir, exist_ok=True)
                        
                        keep_paths = [file_options[i-1][1] for i in selected_indices]
                        kept_names = []
                        
                        # ย้ายไฟล์ที่ "ไม่ถูกเลือก" ไปไว้ที่โฟลเดอร์สำรอง
                        for idx, filepath, filename, slug_display in file_options:
                            if filepath in keep_paths:
                                kept_names.append(slug_display)
                            else:
                                shutil.move(filepath, os.path.join(backup_dir, filename))
                                
                        print(f"   ✅ เก็บไฟล์ไว้รันต่อ: {', '.join(kept_names)}")
                        print(f"   🧹 ย้ายไฟล์จังหวัดที่เหลือไปสำรองที่ {os.path.basename(backup_dir)} (จะรันใหม่เฉพาะจังหวัดที่ย้าย)")
                        return True
                
                print(f"❌ เลือกไม่ถูกต้อง กรุณาเลือกหมายเลขระหว่าง 1 ถึง {len(file_options)}")



