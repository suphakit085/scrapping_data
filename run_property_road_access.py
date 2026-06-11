import argparse
import os
import sys

from utils.property_road_access import (
    DEFAULT_DIRECT_MAJOR_DISTANCE_M,
    DEFAULT_MAX_SNAP_DISTANCE_M,
    build_property_road_access_outputs,
)


if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def _repo_path(script_dir, path):
    return path if os.path.isabs(path) else os.path.join(script_dir, path)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Calculate local road access distance from property points to the nearest major road exit."
    )
    parser.add_argument(
        "--properties-path",
        default="data/raw/property_locations.csv",
        help="Input CSV with property_id/parcel_key, optional id, chanod_no, province, lat, lon.",
    )
    parser.add_argument(
        "--raw-roads-path",
        default="data/raw/roads_raw.json",
        help="Raw OSM road JSON with node_ids and geometry.",
    )
    parser.add_argument(
        "--roads-final-path",
        default="data/processed/roads_final.csv",
        help="Road CSV used to join road_display_name by osm_id.",
    )
    parser.add_argument(
        "--output-path",
        default="data/processed/property_road_access.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--geojson-path",
        default="",
        help="Optional route audit GeoJSON path.",
    )
    parser.add_argument(
        "--max-snap-distance-m",
        type=float,
        default=DEFAULT_MAX_SNAP_DISTANCE_M,
        help="Maximum distance from a property point to a local/major road candidate.",
    )
    parser.add_argument(
        "--direct-major-distance-m",
        type=float,
        default=DEFAULT_DIRECT_MAJOR_DISTANCE_M,
        help="Distance threshold for treating a property as already on a major road.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of property rows to process. Useful for large CSV pilot runs.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    result = build_property_road_access_outputs(
        properties_path=_repo_path(script_dir, args.properties_path),
        raw_roads_path=_repo_path(script_dir, args.raw_roads_path),
        roads_final_path=_repo_path(script_dir, args.roads_final_path),
        output_path=_repo_path(script_dir, args.output_path),
        geojson_path=_repo_path(script_dir, args.geojson_path) if args.geojson_path else None,
        max_snap_distance_m=args.max_snap_distance_m,
        direct_major_distance_m=args.direct_major_distance_m,
        limit=args.limit,
    )

    print(f"[Success] Property road access output saved to {result['output_path']}")
    if result["geojson_path"]:
        print(f"[Success] Route audit GeoJSON saved to {result['geojson_path']}")
    print(f"[Summary] rows={result['rows']}")
    print("[Summary] status_counts:")
    for status, count in result["status_counts"].items():
        print(f"  {status}: {count}")

    total_local = sum(counts["local_segments"] for counts in result["graph_counts"].values())
    if total_local == 0:
        print(
            "[Warning] No local road segments found. Refresh roads with ROAD_GROUPS=major,local "
            "before using this for soi access routing."
        )


if __name__ == "__main__":
    main()
