import csv
import json
import tempfile
import unittest
from pathlib import Path

from utils.google_road_enrichment import (
    base_road_display_name,
    build_google_road_enrichment_outputs,
    geometry_midpoint,
    normalize_google_route_cache,
    parse_google_route_result,
    should_lookup_row,
)


class GoogleRoadEnrichmentTests(unittest.TestCase):
    def test_parse_google_route_result_extracts_route_component(self):
        result = parse_google_route_result(
            {
                "status": "OK",
                "results": [
                    {
                        "formatted_address": "ถนนมิตรภาพ, ขอนแก่น",
                        "place_id": "abc123",
                        "address_components": [
                            {"long_name": "ขอนแก่น", "types": ["administrative_area_level_1"]},
                            {"long_name": "ถนนมิตรภาพ", "types": ["route"]},
                        ],
                    }
                ],
            }
        )

        self.assertEqual(result["google_match_status"], "matched")
        self.assertEqual(result["google_road_name"], "ถนนมิตรภาพ")
        self.assertEqual(result["google_place_id"], "abc123")

    def test_parse_google_route_result_rejects_unnamed_road(self):
        for route_name in ("Unnamed Road", "\u0e16\u0e19\u0e19\u0e17\u0e35\u0e48\u0e44\u0e21\u0e48\u0e21\u0e35\u0e0a\u0e37\u0e48\u0e2d"):
            result = parse_google_route_result(
                {
                    "status": "OK",
                    "results": [
                        {
                            "address_components": [
                                {"long_name": route_name, "types": ["route"]},
                            ],
                        }
                    ],
                }
            )

            self.assertEqual(result["google_match_status"], "no_route")
            self.assertEqual(result["google_road_name"], "")

    def test_normalize_google_route_cache_reclassifies_useless_thai_route(self):
        cache = {
            "1": {
                "google_road_name": "\u0e16\u0e19\u0e19\u0e17\u0e35\u0e48\u0e44\u0e21\u0e48\u0e21\u0e35\u0e0a\u0e37\u0e48\u0e2d",
                "google_match_status": "matched",
                "road_display_name": "\u0e16\u0e19\u0e19\u0e17\u0e35\u0e48\u0e44\u0e21\u0e48\u0e21\u0e35\u0e0a\u0e37\u0e48\u0e2d",
            },
            "2": {
                "google_road_name": "\u0e16\u0e19\u0e19\u0e21\u0e34\u0e15\u0e23\u0e20\u0e32\u0e1e",
                "google_match_status": "matched",
            },
        }

        self.assertEqual(normalize_google_route_cache(cache), 1)
        self.assertEqual(cache["1"]["google_match_status"], "no_route")
        self.assertEqual(cache["1"]["google_road_name"], "")
        self.assertEqual(cache["2"]["google_match_status"], "matched")

    def test_parse_google_route_result_preserves_api_error_message(self):
        result = parse_google_route_result(
            {
                "status": "REQUEST_DENIED",
                "error_message": "This API project is not authorized.",
                "results": [],
            }
        )

        self.assertEqual(result["google_match_status"], "api_error")
        self.assertEqual(result["google_api_status"], "REQUEST_DENIED")
        self.assertEqual(result["google_error_message"], "This API project is not authorized.")

    def test_should_lookup_defaults_to_unnamed_without_ref_only(self):
        self.assertEqual(
            should_lookup_row({"road_name": "Road A", "road_ref": ""}),
            (False, "skipped_named"),
        )
        self.assertEqual(
            should_lookup_row({"road_name": "unnamed:1", "road_ref": "218"}),
            (False, "skipped_has_ref"),
        )
        self.assertEqual(
            should_lookup_row({"road_name": "unnamed:1", "road_ref": ""}),
            (True, ""),
        )

    def test_base_display_prefers_osm_name_google_then_ref(self):
        self.assertEqual(
            base_road_display_name({"road_name": "Mittraphap Road", "road_ref": "2"}, "Google Road"),
            "Mittraphap Road",
        )
        self.assertEqual(
            base_road_display_name({"road_name": "unnamed:1", "road_ref": "2"}, "ถนนมิตรภาพ"),
            "ถนนมิตรภาพ",
        )
        self.assertEqual(
            base_road_display_name({"road_name": "unnamed:1", "road_ref": "2"}),
            "Road 2",
        )

    def test_geometry_midpoint_follows_line_distance(self):
        lat, lon = geometry_midpoint(
            [
                {"lat": 0.0, "lon": 0.0},
                {"lat": 0.0, "lon": 2.0},
            ]
        )

        self.assertAlmostEqual(lat, 0.0, places=5)
        self.assertAlmostEqual(lon, 1.0, places=5)

    def test_build_outputs_uses_cache_and_dry_run_without_api_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            roads_path = root / "roads.csv"
            output_path = root / "roads_enriched.csv"
            cache_path = root / "cache.json"

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
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "province": "Rayong",
                        "road_name": "Rayong Road",
                        "road_ref": "",
                        "highway_type": "primary",
                        "osm_id": "1",
                        "lat": "12.0",
                        "lon": "101.0",
                        "length_km": "1.0",
                    }
                )
                writer.writerow(
                    {
                        "province": "Rayong",
                        "road_name": "unnamed:2",
                        "road_ref": "36",
                        "highway_type": "primary",
                        "osm_id": "2",
                        "lat": "12.1",
                        "lon": "101.1",
                        "length_km": "1.0",
                    }
                )
                writer.writerow(
                    {
                        "province": "Rayong",
                        "road_name": "unnamed:3",
                        "road_ref": "",
                        "highway_type": "secondary",
                        "osm_id": "3",
                        "lat": "12.2",
                        "lon": "101.2",
                        "length_km": "1.0",
                    }
                )
                writer.writerow(
                    {
                        "province": "Rayong",
                        "road_name": "unnamed:4",
                        "road_ref": "",
                        "highway_type": "secondary",
                        "osm_id": "4",
                        "lat": "12.3",
                        "lon": "101.3",
                        "length_km": "1.0",
                    }
                )

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "3": {
                            "google_road_name": "ถนนสุขุมวิท",
                            "google_formatted_address": "ถนนสุขุมวิท, ระยอง",
                            "google_place_id": "place-3",
                            "google_match_status": "matched",
                        }
                    },
                    f,
                )

            result = build_google_road_enrichment_outputs(
                roads_path=str(roads_path),
                output_path=str(output_path),
                cache_path=str(cache_path),
                dry_run=True,
            )

            with open(output_path, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(result["rows"], 4)
        self.assertEqual(result["lookups_selected"], 1)
        self.assertEqual(result["cache_hits"], 1)
        self.assertEqual(result["cache_normalizations"], 0)
        self.assertEqual(rows[0]["google_match_status"], "skipped_named")
        self.assertEqual(rows[0]["road_display_name"], "Rayong Road")
        self.assertEqual(rows[1]["google_match_status"], "skipped_has_ref")
        self.assertEqual(rows[1]["road_display_name"], "Road 36")
        self.assertEqual(rows[2]["google_match_status"], "matched")
        self.assertEqual(rows[2]["road_display_name"], "ถนนสุขุมวิท")
        self.assertEqual(rows[3]["google_match_status"], "dry_run")
        self.assertEqual(rows[3]["google_api_status"], "DRY_RUN")
        self.assertEqual(rows[3]["road_display_name"], "unnamed:4")


if __name__ == "__main__":
    unittest.main()
