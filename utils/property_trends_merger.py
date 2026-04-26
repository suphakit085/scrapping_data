"""
Property Trends Merger
รวมข้อมูลราคาอสังหาริมทรัพย์จากหลายแหล่ง:
  - LivingInsider
  - Baania
  - DotProperty (optional)

Canonical output: data/processed/property_trends.csv
"""

import json
import os
import pandas as pd


MOCK_REIC_SOURCES = {
    "REIC (Real Estate Information Center)",
    "REIC",
}


# Province name normalization (Thai → English)
PROVINCE_MAP = {
    "ขอนแก่น":        "Khon Kaen",
    "อุบลราชธานี":    "Ubon Ratchathani",
    "ประจวบคีรีขันธ์": "Prachuap Khiri Khan",
    "อุดรธานี":       "Udon Thani",
    "ระยอง":          "Rayong",
    "ชลบุรี":         "Chonburi",
    "สุรินทร์":        "Surin",
    "บุรีรัมย์":       "Buriram",
    "พิษณุโลก":       "Phitsanulok",
    "เชียงราย":       "Chiang Rai",
}

# Property type normalization (Baania → canonical)
PTYPE_MAP = {
    "House":     "House",
    "Townhome":  "Townhouse",
    "Condo":     "Condo",
    "Townhouse": "Townhouse",
    "Land":      "Land",
}


def _load_source(path, default_source_name, blocked_sources=None):
    """โหลดไฟล์ JSON trend และปรับ Province/Type ให้ Standard"""
    if not path or not os.path.exists(path):
        print(f"  [SKIP] {default_source_name}: file not found at {path}")
        return []

    with open(path, encoding="utf-8") as f:
        records = json.load(f)

    normalized = []
    blocked_count = 0
    for r in records:
        source_name = (r.get("source") or default_source_name).strip()
        if blocked_sources and source_name in blocked_sources:
            blocked_count += 1
            continue

        prov_th = r.get("province", "")
        prov_en = r.get("province_en") or PROVINCE_MAP.get(prov_th, prov_th)
        ptype   = PTYPE_MAP.get(r.get("property_type", ""), r.get("property_type", ""))
        median  = r.get("median_price", 0)
        count   = r.get("sample_count", 0)

        if not prov_en or not ptype or not median or median <= 0:
            continue

        normalized.append({
            "province":      prov_en,
            "property_type": ptype,
            "median_price":  float(median),
            "sample_count":  int(count),
            "source":        source_name,
        })

    print(f"  [OK] {default_source_name}: {len(normalized)} valid records loaded")
    if blocked_count:
        print(f"  [SKIP] {default_source_name}: {blocked_count} blocked mock row(s)")
    return normalized


def merge_property_trends(
    baania_path,
    livinginsider_path,
    output_path,
    dotproperty_path=None,
    include_dotproperty=True,
):
    """
    รวมข้อมูลจากทั้งสองแหล่ง โดยใช้ Weighted Median ตาม Sample Count
    จังหวัด + ประเภทอสังหาฯ เดียวกัน → รวมเป็น 1 แถว
    """
    print("\n[Property Trends Merger] Starting...")

    all_records = []
    all_records.extend(_load_source(livinginsider_path, "LivingInsider"))
    all_records.extend(_load_source(baania_path,        "Baania"))
    if include_dotproperty:
        all_records.extend(
            _load_source(
                dotproperty_path,
                "DotProperty",
                blocked_sources=MOCK_REIC_SOURCES,
            )
        )
    else:
        print("  [SKIP] DotProperty: disabled (set include_dotproperty=True to enable)")

    if not all_records:
        print("  [ERROR] No data to merge.")
        return

    df = pd.DataFrame(all_records)

    # Group by Province + PropertyType → สร้าง Weighted Average Median
    results = []
    for (prov, ptype), grp in df.groupby(["province", "property_type"]):
        # Weighted average ตาม sample_count
        total_samples = grp["sample_count"].sum()
        if total_samples == 0:
            continue

        weighted_median = (
            (grp["median_price"] * grp["sample_count"]).sum() / total_samples
        )
        source_list = ", ".join(grp["source"].unique())

        results.append({
            "province":         prov,
            "property_type":    ptype,
            "median_price":     round(weighted_median, 0),
            "total_samples":    int(total_samples),
            "source_count":     len(grp),
            "sources":          source_list,
        })

    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values(["province", "property_type"])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"\n  Merged Trends Summary ({len(result_df)} rows):")
    print(result_df[["province", "property_type", "median_price", "total_samples", "sources"]].to_string(index=False))
    print(f"\n  [Saved] -> {output_path}")

    return result_df


if __name__ == "__main__":
    merge_property_trends(
        baania_path="data/raw/baania_trends_raw.json",
        livinginsider_path="data/raw/livinginsider_trends_raw.json",
        output_path="data/processed/property_trends.csv",
        dotproperty_path="data/raw/dotproperty_trends_raw.json",
        include_dotproperty=True,
    )
