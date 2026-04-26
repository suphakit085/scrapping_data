from playwright.sync_api import sync_playwright
import json
import os
import time
import re
import statistics
import random
from urllib.parse import quote

def scrape_baania_micro_trends(output_path):
    print("--- Starting Robust Baania Micro-Zone Scraper (v5.2) ---")
    
    provinces = [
        "ขอนแก่น", "อุบลราชธานี", "ประจวบคีรีขันธ์", "อุดรธานี", 
        "ระยอง", "ชลบุรี", "สุรินทร์", "บุรีรัมย์", "พิษณุโลก", "เชียงราย"
    ]
    
    # 1=House, 2=Townhome, 3=Condo
    property_types = [
        {"en": "House", "type_id": "1"},
        {"en": "Townhome", "type_id": "2"},
        {"en": "Condo", "type_id": "3"}
    ]
    
    all_listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 1000}
        )
        page = context.new_page()

        for province in provinces:
            for ptype in property_types:
                ptype_en = ptype["en"]
                tid = ptype["type_id"]
                
                encoded_province = quote(province)
                # ดึงอย่างน้อย 2 หน้าแรกต่อหมวดหมู่เพื่อให้ได้ข้อมูลที่สมเหตุสมผล
                for page_num in range(1, 3): 
                    url = f"https://www.baania.com/th/s/{encoded_province}/project?propertyType={tid}&page={page_num}"
                    
                    print(f"Scraping {province} - {ptype_en} (Page {page_num})...")
                    
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(4000)
                        
                        # ดึงทุกกล่องที่เป็นโครงการ
                        cards = page.query_selector_all("a[href*='/project/']")
                        
                        found_in_page = 0
                        for card in cards:
                            try:
                                text_content = card.inner_text()
                                # 1. แงะราคาด้วย Regex
                                price_match = re.search(r'([\d,.]+)\s*(ล้าน)?\s*บาท', text_content)
                                if not price_match: continue
                                
                                val_str = price_match.group(1).replace(',', '')
                                val = float(val_str)
                                if price_match.group(2) == 'ล้าน':
                                    val *= 1000000
                                
                                # 2. แงะทำเล (บรรทัดที่มักจะมีชื่อตำบล อำเภอ จังหวัด)
                                lines = [l.strip() for l in text_content.split('\n') if l.strip()]
                                # ทำเลมักจะอยู่บรรทัดที่ 2 หรือ 3 ที่มีคำว่า เมือง หรือ จังหวัด
                                location_line = ""
                                for line in lines:
                                    if province in line:
                                        location_line = line
                                        break
                                
                                if not location_line: continue
                                
                                parts = location_line.split()
                                tambon = parts[0] if len(parts) > 0 else "Unknown"
                                amphoe = parts[1] if len(parts) > 1 else "Unknown"
                                
                                all_listings.append({
                                    "province": province,
                                    "amphoe": amphoe.replace("เมือง", "").replace("อำเภอ", "").strip(),
                                    "tambon": tambon.replace("ตำบล", "").replace("แขวง", "").strip(),
                                    "property_type": ptype_en,
                                    "price": val,
                                    "source": "Baania"
                                })
                                found_in_page += 1
                            except: continue

                        print(f"  -> Extracted {found_in_page} listings with prices.")
                        if found_in_page == 0: break # ถ้าหน้าไหนไม่มีราคาเลย อาจจะหมดหน้าที่มีข้อมูลแล้ว

                    except Exception as e:
                        print(f"  -> Error on page {page_num}: {e}")
                        break
                
                time.sleep(random.uniform(1, 2))

        browser.close()

    if all_listings:
        # บันทึกข้อมูลดิบ
        raw_output = output_path.replace(".json", "_raw_listings.json")
        with open(raw_output, "w", encoding="utf-8") as f:
            json.dump(all_listings, f, ensure_ascii=False, indent=2)
        
        # สรุปข้อมูลรายตำบล
        import pandas as pd
        df = pd.DataFrame(all_listings)
        summary = df.groupby(["province", "amphoe", "tambon", "property_type"])["price"].median().reset_index()
        summary.columns = ["province", "amphoe", "tambon", "property_type", "median_price"]
        
        summary.to_json(output_path, orient="records", force_ascii=False, indent=2)
        print(f"\n[Success] Micro-Zone trends saved to {output_path}")
        print(f"Total listings collected: {len(all_listings)}")
    else:
        print("[Error] No listings with prices could be extracted.")

if __name__ == "__main__":
    scrape_baania_micro_trends("data/raw/baania_trends_raw.json")
