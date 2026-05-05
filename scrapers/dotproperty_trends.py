import requests
from bs4 import BeautifulSoup
import re
import json
import os
import time

def scrape_dotproperty_micro_trends(output_path):
    print("--- Starting DotProperty Micro-Zone Scraper (Tambon Level) ---")
    
    province_map = {
        "ขอนแก่น": "khon-kaen", "อุบลราชธานี": "ubon-ratchathani",
        "ประจวบคีรีขันธ์": "prachuap-khiri-khan", "อุดรธานี": "udon-thani",
        "ระยอง": "rayong", "ชลบุรี": "chonburi", "สุรินทร์": "surin",
        "บุรีรัมย์": "buriram", "พิษณุโลก": "phitsanulok", "เชียงราย": "chiang-rai"
    }
    
    all_listings = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for thai_name, slug in province_map.items():
        url = f"https://www.dotproperty.co.th/en/properties-for-sale/{slug}"
        print(f"Scraping {thai_name}...")
        
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # มองหากล่องประกาศ
                cards = soup.select('.search-listing, div[class*="listing"]')
                
                for card in cards:
                    text = card.get_text()
                    
                    # 1. แงะราคา
                    price_match = re.search(r'฿\s*([\d,]+)', text)
                    if not price_match: continue
                    
                    val = float(price_match.group(1).replace(',', ''))
                    if val < 100000: continue
                    
                    # 2. แงะชื่อตำบล (มักจะอยู่หลัง comma หรือระบุว่า Tambon)
                    tambon = "Unknown"
                    tambon_match = re.search(r'Tambon\s+([A-Za-z\s]+),', text)
                    if not tambon_match:
                        # ลองภาษาไทยถ้ามี
                        tambon_match = re.search(r'(ตำบล|ต\.)\s*([ก-๙]+)', text)
                    
                    if tambon_match:
                        tambon = tambon_match.group(2).strip() if len(tambon_match.groups()) >= 2 else tambon_match.group(1).strip()

                    # 3. ระบุประเภท
                    ptype = "House"
                    if "Condo" in text or "คอนโด" in text: ptype = "Condo"
                    elif "Townhouse" in text or "ทาวน์" in text: ptype = "Townhome"
                    
                    all_listings.append({
                        "province": thai_name,
                        "tambon": tambon,
                        "property_type": ptype,
                        "price": val,
                        "source": "DotProperty"
                    })
        except: pass
        time.sleep(1.5)

    if all_listings:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_listings, f, ensure_ascii=False, indent=2)
        print(f"\n[Success] DotProperty Micro-listings saved to {output_path}")

if __name__ == "__main__":
    scrape_dotproperty_micro_trends("data/raw/dotproperty_trends_raw.json")
