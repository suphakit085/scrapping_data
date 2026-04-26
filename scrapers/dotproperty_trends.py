import requests
from bs4 import BeautifulSoup
import re
import json
import os
import time
import statistics

def scrape_dotproperty_trends(output_path):
    print("Starting Deep Analytics DotProperty Scraper...")
    
    province_map = {
        "ขอนแก่น": "khon-kaen",
        "อุบลราชธานี": "ubon-ratchathani",
        "ประจวบคีรีขันธ์": "prachuap-khiri-khan",
        "อุดรธานี": "udon-thani",
        "ระยอง": "rayong",
        "ชลบุรี": "chonburi",
        "สุรินทร์": "surin",
        "บุรีรัมย์": "buriram",
        "พิษณุโลก": "phitsanulok",
        "เชียงราย": "chiang-rai"
    }
    
    final_results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for thai_name, slug in province_map.items():
        url = f"https://www.dotproperty.co.th/en/properties-for-sale/{slug}"
        print(f"Deep scraping {thai_name}...")
        
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                html = response.text
                
                # Extract listing data points
                listings = soup.select('a.no-title')
                
                # Group data by type
                data_by_type = {
                    "House": {"prices": [], "sqm": []},
                    "Condo": {"prices": [], "sqm": []},
                    "Land": {"prices": [], "sqm": []},
                    "Townhouse": {"prices": [], "sqm": []}
                }
                
                for item in listings:
                    text = item.get_text()
                    
                    # Detect Property Type
                    current_type = "Other"
                    for ptype in data_by_type.keys():
                        if ptype in text:
                            current_type = ptype
                            break
                    
                    if current_type == "Other": continue

                    # Extract Price
                    price_match = re.search(r'฿\s*([\d,]+)', text)
                    if price_match:
                        p = float(price_match.group(1).replace(',', ''))
                        # Outlier Filter: Ignore suspiciously low or extremely high prices
                        if 100000 < p < 500000000: 
                            data_by_type[current_type]["prices"].append(p)
                    
                    # Extract Sqm
                    sqm_match = re.search(r'([\d,.]+)\s*SqM', text)
                    if sqm_match:
                        s = float(sqm_match.group(1).replace(',', ''))
                        if s > 0:
                            data_by_type[current_type]["sqm"].append(s)

                # Process stats for each type in this province
                for ptype, samples in data_by_type.items():
                    prices = samples["prices"]
                    sqm = samples["sqm"]
                    
                    if not prices: continue # Skip if no data for this type
                    
                    avg_price = sum(prices) / len(prices)
                    median_price = statistics.median(prices)
                    avg_sqm = sum(sqm) / len(sqm) if sqm else 0
                    price_per_sqm = avg_price / avg_sqm if avg_sqm > 0 else 0
                    
                    final_results.append({
                        "province": thai_name,
                        "province_en": slug.replace('-', ' ').title(),
                        "property_type": ptype,
                        "sample_count": len(prices),
                        "average_price": round(avg_price, 2),
                        "median_price": round(median_price, 2),
                        "average_sqm": round(avg_sqm, 2),
                        "price_per_sqm": round(price_per_sqm, 2),
                        "currency": "THB",
                        "source": "DotProperty",
                        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                
                print(f"  - Captured data for {len([t for t, s in data_by_type.items() if s['prices']])} property types.")
            else:
                print(f"  - Failed. Status: {response.status_code}")
        except Exception as e:
            print(f"  - Error: {e}")
            
        time.sleep(2)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, ensure_ascii=False, indent=4)
        
    print(f"Saved DotProperty price data to {output_path}")

if __name__ == "__main__":
    scrape_dotproperty_trends("../data/raw/dotproperty_trends_raw.json")
