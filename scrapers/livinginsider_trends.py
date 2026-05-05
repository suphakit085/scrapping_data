from playwright.sync_api import sync_playwright
import re
import json
import os
import time
import pandas as pd
from urllib.parse import quote

def scrape_livinginsider_micro_trends(output_path):
    print("--- Starting LivingInsider Micro-Zone Scraper (Tambon Level) ---")
    
    province_data = [
        {"name": "ขอนแก่น", "slug": "Khon-Kaen", "zone_id": "47"},
        {"name": "อุบลราชธานี", "slug": "Ubon-Ratchathani", "zone_id": "94"},
        {"name": "ประจวบคีรีขันธ์", "slug": "Prachuap-Khiri-Khan", "zone_id": "43"},
        {"name": "อุดรธานี", "slug": "Udon-Thani", "zone_id": "93"},
        {"name": "ระยอง", "slug": "Rayong", "zone_id": "121"},
        {"name": "ชลบุรี", "slug": "Chonburi", "zone_id": "42"},
        {"name": "สุรินทร์", "slug": "Surin", "zone_id": "89"},
        {"name": "บุรีรัมย์", "slug": "Buriram", "zone_id": "81"},
        {"name": "พิษณุโลก", "slug": "Phitsanulok", "zone_id": "104"},
        {"name": "เชียงราย", "slug": "Chiang-Rai", "zone_id": "111"}
    ]
    
    all_listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for province in province_data:
            thai_name = province["name"]
            zone_id = province["zone_id"]
            slug = province["slug"]
            
            # ดึง 2 หน้าแรกเพื่อความรวดเร็วและได้ตัวอย่างที่เพียงพอ
            for page_num in range(1, 3):
                url = f"https://www.livinginsider.com/living_zone/{zone_id}/all/all/{page_num}/{slug}.html"
                print(f"Scraping {thai_name} (Page {page_num})...")
                
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3000)
                    
                    # ค้นหากล่องประกาศ
                    cards = page.query_selector_all(".item-info, .listing-item, div[class*='item']")
                    
                    for card in cards:
                        try:
                            text = card.inner_text()
                            if "เช่า" in text and "ขาย" not in text: continue
                            
                            # 1. แงะราคา
                            price_match = re.search(r'([\d,]+)\s*(ล้าน)?\s*บาท', text)
                            if not price_match:
                                # ลองหาตัวเลขหลักแสนหลักล้านตรงๆ
                                price_match = re.search(r'([\d,]{6,10})', text)
                                
                            if not price_match: continue
                            
                            val = float(price_match.group(1).replace(',', ''))
                            if "ล้าน" in text and val < 100: val *= 1000000
                            
                            if val < 100000: continue # กรองราคาเช่าที่หลุดมา
                            
                            # 2. แงะชื่อตำบล (มองหาคำว่า ตำบล หรือ แขวง)
                            tambon = "Unknown"
                            tambon_match = re.search(r'(ตำบล|ต\.|แขวง)\s*([ก-๙]+)', text)
                            if tambon_match:
                                tambon = tambon_match.group(2).strip()
                            
                            # 3. ระบุประเภท (คร่าวๆ จาก Keyword)
                            ptype = "House"
                            if "คอนโด" in text: ptype = "Condo"
                            elif "ทาวน์" in text: ptype = "Townhome"
                            
                            all_listings.append({
                                "province": thai_name,
                                "tambon": tambon,
                                "property_type": ptype,
                                "price": val,
                                "source": "LivingInsider"
                            })
                        except: continue
                except: break
                
        browser.close()

    if all_listings:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_listings, f, ensure_ascii=False, indent=2)
        print(f"\n[Success] LivingInsider Micro-listings saved to {output_path}")

if __name__ == "__main__":
    scrape_livinginsider_micro_trends("data/raw/livinginsider_trends_raw.json")
