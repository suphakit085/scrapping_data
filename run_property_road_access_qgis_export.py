import argparse
import os
import sys

from utils.property_road_access_qgis import (
    DEFAULT_ISSUE_STATUSES,
    export_property_points_geojson,
)


if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def _repo_path(script_dir, path):
    return path if os.path.isabs(path) else os.path.join(script_dir, path)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export property road access point GeoJSON for QGIS audit layers."
    )
    parser.add_argument(
        "--csv-path",
        default="data/processed/property_road_access_khonkaen.csv",
        help="Input property_road_access CSV.",
    )
    parser.add_argument(
        "--points-output-path",
        default="data/processed/property_road_access_khonkaen_issue_points.geojson",
        help="Output point GeoJSON path.",
    )
    parser.add_argument(
        "--statuses",
        default=",".join(sorted(DEFAULT_ISSUE_STATUSES)),
        help="Comma-separated routing_status values to export. Empty string exports all statuses.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of point features to export.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    statuses = None if args.statuses == "" else args.statuses
    result = export_property_points_geojson(
        csv_path=_repo_path(script_dir, args.csv_path),
        output_path=_repo_path(script_dir, args.points_output_path),
        statuses=statuses,
        limit=args.limit,
    )

    print(f"[Success] Point GeoJSON saved to {result['output_path']}")
    print(f"[Summary] features={result['features']}")
    print(f"[Summary] statuses={', '.join(result['statuses']) if result['statuses'] else 'all'}")


if __name__ == "__main__":
    main()
