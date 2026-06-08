import csv
import tempfile
import unittest
from pathlib import Path

from utils.road_intelligence import (
    ROAD_FEATURE_FIELDNAMES,
    ROAD_SUMMARY_FIELDNAMES,
    build_road_density_by_zone,
    build_road_feature_row,
    build_road_features,
    build_road_intelligence_outputs,
    build_road_intersections,
    build_summary_by_province,
    oneway_status,
    surface_group,
)


class RoadIntelligenceTests(unittest.TestCase):
    def test_road_feature_row_preserves_missing_as_flags(self):
        row = build_road_feature_row(
            {
                "province": "Buri Ram",
                "road_name": "unnamed:1",
                "road_ref": "218",
                "highway_type": "primary",
                "osm_id": "1",
                "lat": "14.0",
                "lon": "102.0",
                "length_km": "0.049",
                "lanes": "",
                "oneway": "",
                "surface": "asphalt",
                "is_bridge": "False",
            }
        )

        self.assertEqual(row["road_display_name"], "Road 218")
        self.assertTrue(row["lanes_missing"])
        self.assertEqual(row["oneway_status"], "unknown")
        self.assertEqual(row["surface_group"], "paved")
        self.assertTrue(row["has_road_ref"])
        self.assertTrue(row["is_unnamed"])
        self.assertTrue(row["is_short_segment"])

    def test_oneway_status_and_surface_group(self):
        self.assertEqual(oneway_status("yes"), "one_way")
        self.assertEqual(oneway_status("-1"), "one_way")
        self.assertEqual(oneway_status("no"), "two_way")
        self.assertEqual(oneway_status("reversible"), "unknown")
        self.assertEqual(surface_group("concrete"), "paved")
        self.assertEqual(surface_group("gravel"), "unpaved")
        self.assertEqual(surface_group(""), "unknown")

    def test_summary_by_province_aggregates_segments(self):
        rows = build_road_features(
            [
                {
                    "province": "Rayong",
                    "road_name": "Road A",
                    "road_ref": "36",
                    "highway_type": "primary",
                    "osm_id": "1",
                    "lat": "12.0",
                    "lon": "101.0",
                    "length_km": "1.5",
                    "lanes": "2",
                    "oneway": "yes",
                    "surface": "asphalt",
                    "is_bridge": "False",
                },
                {
                    "province": "Rayong",
                    "road_name": "unnamed:2",
                    "road_ref": "",
                    "highway_type": "trunk",
                    "osm_id": "2",
                    "lat": "12.1",
                    "lon": "101.1",
                    "length_km": "2.0",
                    "lanes": "",
                    "oneway": "",
                    "surface": "",
                    "is_bridge": "True",
                },
            ]
        )

        summary = build_summary_by_province(rows)[0]

        self.assertEqual(list(summary.keys()), ROAD_SUMMARY_FIELDNAMES)
        self.assertEqual(summary["segment_count"], 2)
        self.assertEqual(summary["total_length_km"], "3.500")
        self.assertEqual(summary["primary_km"], "1.500")
        self.assertEqual(summary["trunk_km"], "2.000")
        self.assertEqual(summary["named_pct"], "50.0")
        self.assertEqual(summary["ref_coverage_pct"], "50.0")

    def test_duplicate_osm_id_is_rejected(self):
        rows = [
            {
                "province": "Rayong",
                "road_name": "Road A",
                "road_ref": "36",
                "highway_type": "primary",
                "osm_id": "1",
                "lat": "12.0",
                "lon": "101.0",
                "length_km": "1.0",
                "lanes": "",
                "oneway": "",
                "surface": "",
                "is_bridge": "False",
            },
            {
                "province": "Rayong",
                "road_name": "Road B",
                "road_ref": "36",
                "highway_type": "primary",
                "osm_id": "1",
                "lat": "12.1",
                "lon": "101.1",
                "length_km": "1.0",
                "lanes": "",
                "oneway": "",
                "surface": "",
                "is_bridge": "False",
            },
        ]

        with self.assertRaisesRegex(ValueError, "duplicate osm_id"):
            build_road_features(rows)

    def test_intersections_from_node_topology(self):
        raw_records = [
            {
                "province": "Rayong",
                "osm_id": 1,
                "highway_type": "primary",
                "node_ids": [10, 20],
                "geometry": [{"lat": 12.0, "lon": 101.0}, {"lat": 12.1, "lon": 101.1}],
            },
            {
                "province": "Rayong",
                "osm_id": 2,
                "highway_type": "secondary",
                "node_ids": [20, 30],
                "geometry": [{"lat": 12.1, "lon": 101.1}, {"lat": 12.2, "lon": 101.2}],
            },
            {
                "province": "Rayong",
                "osm_id": 3,
                "highway_type": "tertiary",
                "node_ids": [40, 20],
                "geometry": [{"lat": 12.3, "lon": 101.3}, {"lat": 12.1, "lon": 101.1}],
            },
        ]

        intersections = build_road_intersections(raw_records)

        self.assertEqual(len(intersections), 1)
        self.assertEqual(intersections[0]["intersection_id"], "osm_node:20")
        self.assertEqual(intersections[0]["connected_way_count"], 3)
        self.assertEqual(intersections[0]["connected_osm_ids"], "1|2|3")

    def test_density_by_zone_counts_nearby_segments(self):
        feature_rows = build_road_features(
            [
                {
                    "province": "Rayong",
                    "road_name": "Road A",
                    "road_ref": "36",
                    "highway_type": "primary",
                    "osm_id": "1",
                    "lat": "12.0000",
                    "lon": "101.0000",
                    "length_km": "1.5",
                    "lanes": "2",
                    "oneway": "yes",
                    "surface": "asphalt",
                    "is_bridge": "False",
                },
                {
                    "province": "Rayong",
                    "road_name": "Road B",
                    "road_ref": "3",
                    "highway_type": "trunk",
                    "osm_id": "2",
                    "lat": "13.0000",
                    "lon": "102.0000",
                    "length_km": "2.0",
                    "lanes": "2",
                    "oneway": "yes",
                    "surface": "asphalt",
                    "is_bridge": "False",
                },
            ]
        )

        density = build_road_density_by_zone(
            feature_rows,
            [{"zone_name": "Anchor", "province": "Rayong", "lat": "12.0001", "lon": "101.0001"}],
            radius_km=2.0,
        )

        self.assertEqual(density[0]["road_segment_count"], 1)
        self.assertEqual(density[0]["total_road_length_km"], "1.500")
        self.assertEqual(density[0]["primary_km"], "1.500")
        self.assertEqual(density[0]["trunk_km"], "0.000")

    def test_build_outputs_writes_expected_schemas(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            roads_path = root / "roads.csv"
            landmarks_path = root / "landmarks_clean.csv"
            features_path = root / "roads_features.csv"
            summary_path = root / "roads_summary_by_province.csv"
            intersections_path = root / "road_intersections.csv"
            density_path = root / "road_density_by_zone.csv"

            with open(roads_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "province",
                        "road_name",
                        "road_ref",
                        "highway_type",
                        "osm_id",
                        "lat",
                        "lon",
                        "length_km",
                        "lanes",
                        "oneway",
                        "surface",
                        "is_bridge",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "province": "Rayong",
                        "road_name": "unnamed:1",
                        "road_ref": "36",
                        "highway_type": "primary",
                        "osm_id": "1",
                        "lat": "12.0",
                        "lon": "101.0",
                        "length_km": "1.0",
                        "lanes": "",
                        "oneway": "",
                        "surface": "",
                        "is_bridge": "False",
                    }
                )

            with open(landmarks_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["province_en", "name", "layer", "lat", "lon"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "province_en": "Rayong",
                        "name": "Anchor",
                        "layer": "1",
                        "lat": "12.0",
                        "lon": "101.0",
                    }
                )

            result = build_road_intelligence_outputs(
                roads_path=str(roads_path),
                raw_roads_path=str(root / "missing_raw.json"),
                features_path=str(features_path),
                summary_path=str(summary_path),
                intersections_path=str(intersections_path),
                density_path=str(density_path),
                zone_profiles_path=str(root / "missing_zone_profiles.csv"),
                landmarks_path=str(landmarks_path),
            )

            with open(features_path, encoding="utf-8-sig", newline="") as f:
                feature_rows = list(csv.DictReader(f))
            with open(summary_path, encoding="utf-8-sig", newline="") as f:
                summary_rows = list(csv.DictReader(f))

        self.assertEqual(result["features"], 1)
        self.assertEqual(result["summaries"], 1)
        self.assertEqual(result["intersections"], 0)
        self.assertEqual(result["density_rows"], 1)
        self.assertEqual(list(feature_rows[0].keys()), ROAD_FEATURE_FIELDNAMES)
        self.assertEqual(list(summary_rows[0].keys()), ROAD_SUMMARY_FIELDNAMES)
        self.assertEqual(feature_rows[0]["road_display_name"], "Road 36")


if __name__ == "__main__":
    unittest.main()
