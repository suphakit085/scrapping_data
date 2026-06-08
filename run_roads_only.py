import os
import sys

from scrapers.road_analysis import fetch_province_roads


if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    raw_output_path = os.path.join(script_dir, "data", "raw", "roads_raw.json")
    raw_quality_report_path = os.path.join(script_dir, "data", "raw", "roads_raw_quality_report.json")
    csv_output_path = os.path.join(script_dir, "data", "processed", "roads.csv")
    temp_dir = os.environ.get(
        "ROAD_CACHE_DIR",
        os.path.join(script_dir, "data", "raw", "temp_roads_topology"),
    )
    groups = os.environ.get("ROAD_GROUPS", "major,local")

    fetch_province_roads(
        raw_output_path=raw_output_path,
        csv_output_path=csv_output_path,
        temp_dir=temp_dir,
        groups=groups,
        require_topology=True,
        raw_quality_report_path=raw_quality_report_path,
    )

    if os.environ.get("BUILD_ROAD_INTELLIGENCE") == "1":
        from utils.road_intelligence import build_road_intelligence_outputs

        build_road_intelligence_outputs(
            roads_path=csv_output_path,
            raw_roads_path=raw_output_path,
            features_path=os.path.join(script_dir, "data", "processed", "roads_features.csv"),
            summary_path=os.path.join(script_dir, "data", "processed", "roads_summary_by_province.csv"),
            intersections_path=os.path.join(script_dir, "data", "processed", "road_intersections.csv"),
            density_path=os.path.join(script_dir, "data", "processed", "road_density_by_zone.csv"),
            zone_profiles_path=os.path.join(script_dir, "data", "processed", "zone_profiles.csv"),
            landmarks_path=os.path.join(script_dir, "data", "processed", "landmarks_clean.csv"),
        )


if __name__ == "__main__":
    main()
