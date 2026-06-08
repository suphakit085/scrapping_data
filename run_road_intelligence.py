import os
import sys

from utils.road_intelligence import build_road_intelligence_outputs


if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    result = build_road_intelligence_outputs(
        roads_path=os.path.join(script_dir, "data", "processed", "roads.csv"),
        raw_roads_path=os.path.join(script_dir, "data", "raw", "roads_raw.json"),
        features_path=os.path.join(script_dir, "data", "processed", "roads_features.csv"),
        summary_path=os.path.join(script_dir, "data", "processed", "roads_summary_by_province.csv"),
        intersections_path=os.path.join(script_dir, "data", "processed", "road_intersections.csv"),
        density_path=os.path.join(script_dir, "data", "processed", "road_density_by_zone.csv"),
        zone_profiles_path=os.path.join(script_dir, "data", "processed", "zone_profiles.csv"),
        landmarks_path=os.path.join(script_dir, "data", "processed", "landmarks_clean.csv"),
    )

    print(
        "[Success] Road intelligence outputs generated: "
        f"{result['features']} features, "
        f"{result['summaries']} province summaries, "
        f"{result['intersections']} intersections, "
        f"{result['density_rows']} zone density rows"
    )


if __name__ == "__main__":
    main()
