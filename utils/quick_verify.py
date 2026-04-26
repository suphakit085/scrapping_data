import pandas as pd
import os

def verify_outputs():
    property_path = "data/processed/property_trends.csv"
    zones_path = "data/processed/zone_profiles.csv"
    
    print("=== Pipeline Quality Check ===")
    
    # 1. Check Property Trends
    if os.path.exists(property_path):
        df_p = pd.read_csv(property_path, encoding='utf-8-sig')
        print(f"\n[1] Property Trends ({len(df_p)} rows):")
        print(f"    - Columns: {list(df_p.columns)}")
        # เช็คแหล่งที่มา
        sources = df_p['sources'].unique()
        print(f"    - Unique Sources found: {sources}")
        if any("REIC" in s for s in sources):
            print("    [!] ALERT: REIC is still mixed in prices!")
        else:
            print("    [OK] Price sources are clean (Baania/LI/DotProperty only).")
    
    # 2. Check Zone Profiles
    if os.path.exists(zones_path):
        df_z = pd.read_csv(zones_path, encoding='utf-8-sig')
        print(f"\n[2] Zone Profiles ({len(df_z)} rows):")
        reic_cols = [c for c in df_z.columns if "reic" in c.lower()]
        print(f"    - REIC Insights Columns: {reic_cols}")
        
        if reic_cols:
            sample = df_z[df_z['province'] == 'ขอนแก่น'].iloc[0]
            print(f"    - Sample Khon Kaen Row:")
            print(f"      > Anchor: {sample['zone_anchor']}")
            print(f"      > Livability Score: {sample['livability_score']}")
            print(f"      > Absorption Rate: {sample.get('reic_absorption_rate', 'N/A')}")
            print(f"      > Market Sentiment: {sample.get('reic_sentiment', 'N/A')}")
            
            # Check for invalid coords (Out of Thailand)
            lat_err = df_z[(df_z['lat'] < 5) | (df_z['lat'] > 21)]
            if not lat_err.empty:
                print(f"    [!] ALERT: Found {len(lat_err)} rows with invalid Latitudes (Russian detected?)")
            else:
                print("    [OK] All coordinates are within Thailand.")
        else:
            print("    [!] ALERT: REIC columns are MISSING from zone profiles!")

if __name__ == "__main__":
    verify_outputs()
