"""
Preprocess Thailand admin boundaries for the project's target provinces.

The source GeoJSON is large, so this script streams features with ijson and
writes only the 10 target provinces used by the landmark pipeline.
"""

import json
import os
import sys
from decimal import Decimal

import ijson
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.geo_boundaries import (
    TARGET_ADMIN3_CENTROIDS_PATH,
    TARGET_BOUNDARY_PATH,
    TARGET_PROVINCES,
    normalize_province_name,
)

INPUT_PATH = "data/the_admin_boundaries.geojson"


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
    admin3_centroids = []

    with open(INPUT_PATH, "rb") as src:
        for feature in ijson.items(src, "features.item"):
            props = feature.get("properties") or {}
            province = normalize_province_name(props.get("adm1_name"))

            if province not in target_names:
                continue

            counts[province] = counts.get(province, 0) + 1
            geom = shape(feature["geometry"])
            geoms_by_province[province].append(geom)

            center_lat = props.get("center_lat")
            center_lon = props.get("center_lon")
            if center_lat is None or center_lon is None:
                centroid = geom.representative_point()
                center_lat = centroid.y
                center_lon = centroid.x

            admin3_centroids.append({
                "province": province,
                "district": props.get("adm2_name") or "",
                "district_th": props.get("adm2_name1") or "",
                "admin3": props.get("adm3_name") or props.get("adm3_ref_n") or "",
                "admin3_th": props.get("adm3_name1") or "",
                "admin3_pcode": props.get("adm3_pcode") or "",
                "lat": center_lat,
                "lon": center_lon,
            })

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

    os.makedirs(os.path.dirname(TARGET_BOUNDARY_PATH), exist_ok=True)
    with open(TARGET_BOUNDARY_PATH, "w", encoding="utf-8") as dst:
        json.dump(
            output,
            dst,
            ensure_ascii=False,
            separators=(",", ":"),
            default=json_default,
        )

    with open(TARGET_ADMIN3_CENTROIDS_PATH, "w", encoding="utf-8") as dst:
        json.dump(
            admin3_centroids,
            dst,
            ensure_ascii=False,
            separators=(",", ":"),
            default=json_default,
        )

    print(f"Saved {len(output_features)} province features to {TARGET_BOUNDARY_PATH}")
    print(f"Saved {len(admin3_centroids)} admin3 centroids to {TARGET_ADMIN3_CENTROIDS_PATH}")
    for province in sorted(target_names):
        print(f"{province}: {counts.get(province, 0)}")


if __name__ == "__main__":
    main()
