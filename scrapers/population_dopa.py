import requests
import pandas as pd
import os

def scrape_population_age_groups(output_path):
    print("--- Fetching Detailed Population & Age Data (Year 2567) ---")
    
    target_provinces = {
        "40": "ขอนแก่น", "34": "อุบลราชธานี", "20": "ชลบุรี", "21": "ระยอง",
        "41": "อุดรธานี", "57": "เชียงราย", "65": "พิษณุโลก", "77": "ประจวบคีรีขันธ์",
        "32": "สุรินทร์", "31": "บุรีรัมย์"
    }
    
    all_results = []
    
    for p_code, p_name in target_provinces.items():
        url = f"https://stat.bora.dopa.go.th/new_stat/file/6712/6712cc{p_code}.txt"
        print(f"  Downloading {p_name} ({p_code})...")
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                content = response.content.decode('utf-8', errors='ignore').replace('\ufeff', '')
                lines = content.splitlines()
                
                current_district = "Unknown"
                
                # บรรทัดแรกคือ รวมจังหวัด (ข้ามไป)
                for line in lines[1:]:
                    cols = line.split('|')
                    if len(cols) > 210:
                        area_name = cols[0].strip()
                        
                        if not area_name: continue
                        
                        # ถ้าเป็น "อำเภอ" (ในไฟล์จะไม่มีคำว่าตำบล)
                        if "ตำบล" not in area_name:
                            current_district = area_name.replace("อำเภอ", "").strip()
                            is_tambon = False
                        else:
                            is_tambon = True
                        
                        area_label = area_name.replace("ตำบล", "").replace("อำเภอ", "").strip()
                        
                        try:
                            m_total = int(cols[217].replace(',', '') or 0)
                            f_total = int(cols[218].replace(',', '') or 0)
                            total = int(cols[219].replace(',', '') or 0)
                            
                            children = sum(int(c.replace(',', '') or 0) for c in cols[1:31])
                            working = sum(int(c.replace(',', '') or 0) for c in cols[31:131])
                            elderly = sum(int(c.replace(',', '') or 0) for c in cols[131:205])
                            
                            all_results.append({
                                "province_name": p_name,
                                "district_name": current_district,
                                "tambon_name": area_label if is_tambon else "",
                                "is_tambon": is_tambon,
                                "total_population": total,
                                "male": m_total,
                                "female": f_total,
                                "age_children": children,
                                "age_working": working,
                                "age_elderly": elderly
                            })
                        except: continue
            else:
                print(f"    [Warning] Failed to download {p_name}")
        except Exception as e:
            print(f"    [Error] {e}")

    if all_results:
        df = pd.DataFrame(all_results)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n[Success] Detailed population data (District & Tambon) saved to {output_path}")
    else:
        print("[Error] No data collected.")

if __name__ == "__main__":
    scrape_population_age_groups("data/processed/population_stats.csv")
