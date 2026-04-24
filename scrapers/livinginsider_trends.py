from playwright.sync_api import sync_playwright
import re
import json
import os
import time
import statistics

def scrape_livinginsider_trends(output_path):
    print("Starting LivingInsider Trends Scraper (Deep Thai Support)...")
    
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
    
    final_results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for province in province_data:
            thai_name = province["name"]
            slug = province["slug"]
            zone_id = province["zone_id"]
            
            # Use direct Thai-encoded URL for better compatibility with Zone ID
            url = f"https://www.livinginsider.com/living_zone/{zone_id}/all/all/1/{slug}.html"
            print(f"Scraping {thai_name}...")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(5000) # Wait for cards to render
                
                # Broad selector to find any listing card
                # Based on the screenshot, these are card-like structures
                cards = page.query_selector_all("div[class*='item'], div[class*='card'], .item-info")
                
                data_by_type = {
                    "House": [],
                    "Condo": [],
                    "Land": [],
                    "Townhouse": []
                }
                
                for card in cards:
                    text = card.inner_text()
                    if not text: continue
                    
                    # 1. Advanced Rent Filtering
                    # กรอง "เช่า" หรือคำที่บ่งบอกว่าเป็นรายเดือนออกให้หมด
                    is_rent = any(k in text for k in ["เช่า", "Rent", "เดือน", "/mo", "/month"])
                    is_sale = any(k in text for k in ["ขาย", "Sale"])
                    if is_rent and not is_sale: continue
                    
                    # 2. Detect Property Type
                    current_type = "Other"
                    if any(k in text for k in ["บ้าน", "Home", "House"]): current_type = "House"
                    elif any(k in text for k in ["คอนโด", "Condo"]): current_type = "Condo"
                    elif any(k in text for k in ["ที่ดิน", "Land"]): current_type = "Land"
                    elif any(k in text for k in ["ทาวน์โฮม", "Townhome", "Townhouse"]): current_type = "Townhouse"
                    
                    if current_type == "Other": continue
                    
                    # 3. Extract Price (Paired)
                    p_val = 0
                    price_matches = re.findall(r'(\d[\d,]+)', text)
                    for m in price_matches:
                        clean_num = m.replace(',', '')
                        try:
                            val = float(clean_num)
                            if val > 150000: # Sale price threshold (1.5แสน ขึ้นไป)
                                p_val = val
                                break
                        except: continue
                    
                    if p_val <= 0: continue

                    # 4. Extract Sqm (Paired)
                    s_val = 0
                    sqm_match = re.search(r'([\d,.]+)\s*(sq\.m|sq\.w|ตร\.ม\.|ตร\.ว\.)', text, re.I)
                    if sqm_match:
                        try:
                            s_val = float(sqm_match.group(1).replace(',', ''))
                            unit = sqm_match.group(2).lower()
                            # ถ้าเป็นที่ดิน หรือเป็นหน่วยตารางวา ให้คูณ 4 เป็นตารางเมตร
                            if "w" in unit or "ว" in unit:
                                s_val = s_val * 4
                        except: pass
                    
                    # 5. Store as paired object
                    entry = {"price": p_val}
                    if s_val > 0:
                        entry["sqm"] = s_val
                        entry["price_per_sqm"] = p_val / s_val
                    
                    data_by_type[current_type].append(entry)

                # Process stats using paired data
                for ptype, entries in data_by_type.items():
                    if not entries: continue
                    
                    prices = [e["price"] for e in entries]
                    sqms = [e["sqm"] for e in entries if "sqm" in e]
                    price_per_sqms = [e["price_per_sqm"] for e in entries if "price_per_sqm" in e]
                    
                    avg_price = sum(prices) / len(prices)
                    med_price = statistics.median(prices)
                    
                    avg_sqm = sum(sqms) / len(sqms) if sqms else 0
                    
                    # Use Median for Price per SQM to avoid outlier distortion
                    med_price_per_sqm = statistics.median(price_per_sqms) if price_per_sqms else 0
                    avg_price_per_sqm = sum(price_per_sqms) / len(price_per_sqms) if price_per_sqms else 0
                    
                    final_results.append({
                        "province": thai_name,
                        "province_en": slug.replace('-', ' '),
                        "property_type": ptype,
                        "sample_count": len(prices),
                        "average_price": round(avg_price, 2),
                        "median_price": round(med_price, 2),
                        "average_sqm": round(avg_sqm, 2),
                        "price_per_sqm": round(med_price_per_sqm or avg_price_per_sqm, 2), # Prefer median
                        "currency": "THB",
                        "source": "LivingInsider",
                        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                
                print(f"  - Captured {len(final_results)} rows total.")
            except Exception as e:
                print(f"  - Error scraping {thai_name}: {e}")

        browser.close()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, ensure_ascii=False, indent=4)
        
    print(f"\nFinal: Saved {len(final_results)} records from LivingInsider to {output_path}")

if __name__ == "__main__":
    scrape_livinginsider_trends("../data/raw/livinginsider_trends_raw.json")
