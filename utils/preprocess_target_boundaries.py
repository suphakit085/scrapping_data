"""
Preprocess Thailand admin boundaries for the project's target provinces.

The source GeoJSON is large, so this script streams features with ijson and
writes only the 10 target provinces used by the landmark pipeline.
"""

import json
import os
import re
from decimal import Decimal

import ijson
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


INPUT_PATH = "data/the_admin_boundaries.geojson"
OUTPUT_PATH = "data/raw/target_admin_boundaries.geojson"


TARGET_PROVINCES = {
    "Khon Kaen",
    "Ubon Ratchathani",
    "Prachuap Khiri Khan",
    "Udon Thani",
    "Rayong",
    "Chon Buri",
    "Surin",
    "Buri Ram",
    "Phitsanulok",
    "Chiang Rai",
}


PROVINCE_ALIASES = {
    "chonburi": "Chon Buri",
    "chon buri": "Chon Buri",
    "buriram": "Buri Ram",
    "buri ram": "Buri Ram",
    "prachuapkhirikhan": "Prachuap Khiri Khan",
    "prachuap khiri khan": "Prachuap Khiri Khan",
}


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

    for target in TARGET_PROVINCES:
        target_key = re.sub(r"[^a-z0-9]+", " ", target.lower()).strip()
        if key == target_key or compact_key == target_key.replace(" ", ""):
            return target

    return cleaned


def json_default(value):
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def main():
    target_names = {normalize_province_name(name) for name in TARGET_PROVINCES}
    counts = {}
    geoms_by_province = {name: [] for name in target_names}

    with open(INPUT_PATH, "rb") as src:
        for feature in ijson.items(src, "features.item"):
            props = feature.get("properties") or {}
            province = normalize_province_name(props.get("adm1_name"))

            if province not in target_names:
                continue

            counts[province] = counts.get(province, 0) + 1
            geoms_by_province[province].append(shape(feature["geometry"]))

    output_features = []
    for province in sorted(target_names):
        province_geoms = geoms_by_province.get(province) or []
        if not province_geoms:
            continue

        province_geom = unary_union(province_geoms)
        output_features.append({
            "type": "Feature",
            "properties": {
                "adm1_name": province,
                "adm1_name_normalized": province,
                "source_feature_count": counts.get(province, 0),
            },
            "geometry": mapping(province_geom),
        })

    output = {
        "type": "FeatureCollection",
        "name": "target_admin_boundaries",
        "features": output_features,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as dst:
        json.dump(
            output,
            dst,
            ensure_ascii=False,
            separators=(",", ":"),
            default=json_default,
        )

    print(f"Saved {len(output_features)} province features to {OUTPUT_PATH}")
    for province in sorted(target_names):
        print(f"{province}: {counts.get(province, 0)}")


if __name__ == "__main__":
    main()
