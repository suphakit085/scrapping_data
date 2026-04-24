from playwright.sync_api import sync_playwright
import re
import json
import os
import time
import statistics
import random
from urllib.parse import quote

def scrape_baania_trends(output_path):
    print("Starting Baania Stealth Scraper (10 Provinces - Fix Baht Regex)...")
    
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
    
    final_results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for province in provinces:
            for ptype in property_types:
                ptype_en = ptype["en"]
                tid = ptype["type_id"]
                
                encoded_province = quote(province)
                url = f"https://www.baania.com/th/s/{encoded_province}/project?propertyType={tid}"
                
                print(f"Scraping {province} - {ptype_en}...")
                
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    time.sleep(5)
                    
                    # Scroll to trigger lazy loads
                    page.mouse.wheel(0, 2000)
                    time.sleep(2)
                    
                    content = page.content()
                    
                    # New Regex: Look for numbers followed by 'บาท' or 'ล้าน'
                    # Matches: 2,290,000 บาท, 2.5 ล้านบาท, ฿ 2,500,000
                    # Pattern: Currency symbol (opt) -> Number -> Space (opt) -> Unit
                    price_pattern = r'(?:฿\s*)?([\d,.]+)\s*(ล้าน)?\s*(?:บาท)?'
                    matches = re.findall(price_pattern, content)
                    
                    found_prices = []
                    for val_str, unit_million in matches:
                        try:
                            # Clean up commas
                            clean_val = val_str.replace(',', '')
                            if not clean_val or clean_val == '.': continue
                            
                            val = float(clean_val)
                            if unit_million: val *= 1000000
                            
                            # Validation: Real estate prices are typically > 100k
                            if 100000 < val < 500000000:
                                found_prices.append(val)
                        except: continue

                    if found_prices:
                        found_prices = list(set(found_prices)) # Deduplicate
                        
                        avg_price = sum(found_prices) / len(found_prices)
                        median_price = statistics.median(found_prices)
                        
                        final_results.append({
                            "province": province,
                            "property_type": ptype_en,
                            "sample_count": len(found_prices),
                            "average_price": round(avg_price, 2),
                            "median_price": round(median_price, 2),
                            "source": "Baania",
                            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                        })
                        print(f"  -> Success: Found {len(found_prices)} listings.")
                    else:
                        print("  -> No valid prices found (maybe 'Contact Project' only).")

                except Exception as e:
                    print(f"  -> Error: {e}")
                
                time.sleep(random.uniform(1, 3))

        browser.close()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, ensure_ascii=False, indent=4)
        
    print(f"\nFinal: Captured {len(final_results)} records.")

if __name__ == "__main__":
    scrape_baania_trends("../data/raw/baania_trends_raw.json")
