import csv
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scrapers.road_analysis import (
    _build_province_road_query,
    _build_roads_raw_quality_report,
    _dedupe_road_records,
    _fetch_province_group,
    _fetch_split_group_with_cache,
    _fetch_tile_with_cache,
    _normalize_road_record,
    _overpass_urls,
    _province_tiles,
    _records_have_raw_contract,
    _records_have_topology,
    _road_csv_row,
    _selected_provinces,
    _selected_road_groups,
    _split_bbox,
    _write_roads_csv,
    fetch_province_roads,
)


class RoadAnalysisTests(unittest.TestCase):
    def test_build_province_query_uses_target_boundary_bbox(self):
        query = _build_province_road_query("Buri Ram", ["primary"])

        bbox_match = re.search(r"\((14\.\d+),(102\.\d+),(15\.\d+),(103\.\d+)\)", query)
        self.assertIsNotNone(bbox_match)
        self.assertNotIn("area[", query)
        self.assertIn('"highway"~"^(primary)$"', query)
        self.assertIn("out body geom;", query)

    def test_default_overpass_endpoint_prefers_working_mirror(self):
        self.assertEqual(
            _overpass_urls()[0],
            "https://overpass-api.de/api/interpreter",
        )
        self.assertNotIn("overpass.osm.ch", ",".join(_overpass_urls()))

    def test_overpass_urls_remove_accidental_whitespace(self):
        with patch.dict(
            "os.environ",
            {"OVERPASS_URLS": "https://overpass.osm.vi-di.fr/api/\n  interpreter"},
        ):
            self.assertEqual(
                _overpass_urls(),
                ["https://overpass.osm.vi-di.fr/api/interpreter"],
            )

    def test_selected_road_groups_can_select_major_only(self):
        self.assertEqual(list(_selected_road_groups(["major"])), ["major"])

    def test_selected_provinces_can_read_env_subset(self):
        with patch.dict("os.environ", {"ROAD_PROVINCES": "Surin, Khon Kaen"}):
            self.assertEqual(_selected_provinces(), ["Khon Kaen", "Surin"])

    def test_province_tiles_split_large_boundary_bbox(self):
        tiles = _province_tiles("Khon Kaen", tile_degrees=0.5)

        self.assertGreater(len(tiles), 1)
        first = tiles[0]
        self.assertEqual(len(first), 4)
        self.assertLess(first[0], first[2])
        self.assertLess(first[1], first[3])

    def test_split_bbox_returns_four_quadrants(self):
        self.assertEqual(
            _split_bbox((0, 0, 2, 2)),
            [(0, 0, 1.0, 1.0), (1.0, 0, 2, 1.0), (0, 1.0, 1.0, 2), (1.0, 1.0, 2, 2)],
        )

    def test_normalize_named_road_record(self):
        element = {
            "type": "way",
            "id": 123,
            "tags": {
                "highway": "primary",
                "name": "Mittraphap Road",
                "ref": "2",
                "lanes": "4",
            },
            "geometry": [
                {"lat": 16.0, "lon": 102.0},
                {"lat": 16.1, "lon": 102.0},
            ],
            "nodes": [10, 20],
        }

        record = _normalize_road_record(element, "Khon Kaen", "major")

        self.assertEqual(record["road_name"], "Mittraphap Road")
        self.assertTrue(record["is_named"])
        self.assertEqual(record["highway_type"], "primary")
        self.assertEqual(record["road_ref"], "2")
        self.assertEqual(record["lanes"], "4")
        self.assertEqual(record["node_ids"], [10, 20])
        self.assertEqual(len(record["geometry"]), 2)
        self.assertRegex(record["fetched_at"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertEqual(record["osm_url"], "https://www.openstreetmap.org/way/123")
        self.assertGreater(record["length_km"], 0)

    def test_normalize_unnamed_road_record(self):
        element = {
            "type": "way",
            "id": 456,
            "tags": {"highway": "residential"},
            "center": {"lat": 16.0, "lon": 102.0},
        }

        record = _normalize_road_record(element, "Chon Buri", "local")

        self.assertEqual(record["road_name"], "unnamed:456")
        self.assertFalse(record["is_named"])
        self.assertEqual(record["lat"], 16.0)
        self.assertEqual(record["lon"], 102.0)

    def test_write_roads_csv_flattened_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "roads.csv"
            _write_roads_csv(
                [
                    {
                        "province": "Rayong",
                        "road_name": "Road 1",
                        "is_named": True,
                        "highway_type": "secondary",
                        "osm_id": 1,
                        "lat": 12.0,
                        "lon": 101.0,
                        "length_km": 2.5,
                        "source": "OpenStreetMap / Overpass API",
                        "osm_url": "https://www.openstreetmap.org/way/1",
                        "extraction_group": "major",
                        "tags": {"name": "Road 1", "ref": "36", "lanes": "2"},
                    }
                ],
                str(csv_path),
            )

            with open(csv_path, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            list(rows[0].keys()),
            [
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
        self.assertEqual(rows[0]["province"], "Rayong")
        self.assertEqual(rows[0]["road_ref"], "36")
        self.assertEqual(rows[0]["osm_id"], "1")
        self.assertEqual(rows[0]["lanes"], "2")
        self.assertNotIn("tags", rows[0])
        self.assertNotIn("has_ref", rows[0])
        self.assertNotIn("source", rows[0])
        self.assertNotIn("maxspeed", rows[0])
        self.assertNotIn("access", rows[0])
        self.assertNotIn("quality_flags", rows[0])
        self.assertNotIn("osm_url", rows[0])

    def test_road_csv_row_analysis_fields(self):
        row = _road_csv_row(
            {
                "province": "Buri Ram",
                "road_name": "unnamed:1",
                "is_named": False,
                "highway_type": "primary",
                "osm_id": 1,
                "length_km": 0.02,
                "extraction_group": "major",
                "tags": {"bridge": "yes", "int_ref": "AH121"},
            },
            [
                "road_ref",
                "is_bridge",
                "surface",
                "oneway",
            ],
        )

        self.assertEqual(row["road_ref"], "")
        self.assertTrue(row["is_bridge"])
        self.assertEqual(row["surface"], "")
        self.assertEqual(row["oneway"], "")

    def test_fetch_province_roads_merges_cached_groups_without_network(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cache_dir = temp_path / "cache"
            cache_dir.mkdir()
            raw_path = temp_path / "roads_raw.json"
            csv_path = temp_path / "roads.csv"

            for group in ("major", "local"):
                with open(cache_dir / f"rayong_{group}.json", "w", encoding="utf-8") as f:
                    json.dump(
                        [
                            {
                                "province": "Rayong",
                                "road_name": "Duplicate Road",
                                "is_named": True,
                                "highway_type": "primary",
                                "osm_id": 99,
                                "lat": 12.0,
                                "lon": 101.0,
                                "length_km": 1.0,
                                "source": "OpenStreetMap / Overpass API",
                                "osm_url": "https://www.openstreetmap.org/way/99",
                                "tags": {},
                            }
                        ],
                        f,
                    )

            records = fetch_province_roads(
                raw_output_path=str(raw_path),
                csv_output_path=str(csv_path),
                provinces=["Rayong"],
                temp_dir=str(cache_dir),
                sleep_seconds=0,
            )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["osm_id"], 99)

    def test_fetch_province_roads_major_only_does_not_require_local_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cache_dir = temp_path / "cache"
            cache_dir.mkdir()
            raw_path = temp_path / "roads_raw.json"
            csv_path = temp_path / "roads.csv"
            with open(cache_dir / "rayong_major.json", "w", encoding="utf-8") as f:
                json.dump(
                    [
                        {
                            "province": "Rayong",
                            "road_name": "Major Road",
                            "is_named": True,
                            "highway_type": "primary",
                            "osm_id": 100,
                        }
                    ],
                    f,
                )

            records = fetch_province_roads(
                raw_output_path=str(raw_path),
                csv_output_path=str(csv_path),
                provinces=["Rayong"],
                groups=["major"],
                temp_dir=str(cache_dir),
                sleep_seconds=0,
            )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["road_name"], "Major Road")

    def test_fetch_split_group_uses_existing_subtype_caches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            for highway_type, osm_id in (
                ("residential", 1),
                ("unclassified", 2),
                ("service", 3),
            ):
                with open(
                    cache_dir / f"rayong_local_{highway_type}.json",
                    "w",
                    encoding="utf-8",
                ) as f:
                    json.dump(
                        [
                            {
                                "province": "Rayong",
                                "road_name": f"Road {osm_id}",
                                "is_named": True,
                                "highway_type": highway_type,
                                "osm_id": osm_id,
                            }
                        ],
                        f,
                    )

            records = _fetch_split_group_with_cache(
                "Rayong",
                "local",
                ["residential", "unclassified", "service"],
                str(cache_dir),
            )

        self.assertEqual([r["osm_id"] for r in records], [1, 2, 3])

    def test_fetch_province_group_falls_back_to_tiles_when_bbox_times_out(self):
        with patch(
            "scrapers.road_analysis._request_overpass",
            side_effect=RuntimeError("timeout"),
        ):
            with patch(
                "scrapers.road_analysis._fetch_split_group_with_cache",
                return_value=[{"osm_id": 1}],
            ) as fetch_split:
                records = _fetch_province_group(
                    "Surin",
                    "major",
                    ["primary", "secondary"],
                    temp_dir="cache",
                    require_topology=True,
                )

        self.assertEqual(records, [{"osm_id": 1}])
        fetch_split.assert_called_once_with(
            "Surin",
            "major",
            ["primary", "secondary"],
            "cache",
            require_topology=True,
        )

    def test_dedupe_road_records_by_osm_id(self):
        records = _dedupe_road_records(
            [
                {"osm_id": 1, "road_name": "A"},
                {"osm_id": 1, "road_name": "A duplicate"},
                {"osm_id": 2, "road_name": "B"},
            ]
        )

        self.assertEqual([r["road_name"] for r in records], ["A", "B"])

    def test_records_have_topology_requires_nodes_matching_geometry(self):
        self.assertTrue(
            _records_have_topology(
                [
                    {
                        "node_ids": [1, 2],
                        "geometry": [{"lat": 12.0, "lon": 101.0}, {"lat": 12.1, "lon": 101.1}],
                    }
                ]
            )
        )
        self.assertFalse(
            _records_have_topology(
                [
                    {
                        "node_ids": [],
                        "geometry": [{"lat": 12.0, "lon": 101.0}],
                    }
                ]
            )
        )

    def test_records_have_raw_contract_requires_fetched_at_but_allows_blank_ref(self):
        self.assertTrue(
            _records_have_raw_contract(
                [
                    {
                        "province": "Rayong",
                        "osm_id": 1,
                        "osm_type": "way",
                        "road_name": "unnamed:1",
                        "road_ref": "",
                        "highway_type": "residential",
                        "extraction_group": "local:residential",
                        "lat": 12.0,
                        "lon": 101.0,
                        "length_km": 0.1,
                        "node_ids": [1, 2],
                        "geometry": [{"lat": 12.0, "lon": 101.0}, {"lat": 12.1, "lon": 101.1}],
                        "tags": {"highway": "residential"},
                        "source": "OpenStreetMap / Overpass API",
                        "osm_url": "https://www.openstreetmap.org/way/1",
                        "fetched_at": "2026-06-04T08:00:00Z",
                    }
                ]
            )
        )
        self.assertFalse(
            _records_have_raw_contract(
                [
                    {
                        "province": "Rayong",
                        "osm_id": 1,
                        "osm_type": "way",
                        "road_name": "unnamed:1",
                        "road_ref": "",
                        "highway_type": "residential",
                        "extraction_group": "local:residential",
                        "lat": 12.0,
                        "lon": 101.0,
                        "length_km": 0.1,
                        "node_ids": [1, 2],
                        "geometry": [{"lat": 12.0, "lon": 101.0}, {"lat": 12.1, "lon": 101.1}],
                        "tags": {"highway": "residential"},
                        "source": "OpenStreetMap / Overpass API",
                        "osm_url": "https://www.openstreetmap.org/way/1",
                    }
                ]
            )
        )

    def test_raw_quality_report_flags_contract_and_topology(self):
        report = _build_roads_raw_quality_report(
            [
                {
                    "province": "Rayong",
                    "osm_id": 1,
                    "highway_type": "primary",
                    "node_ids": [10, 20],
                    "geometry": [
                        {"lat": 12.0, "lon": 101.0},
                        {"lat": 12.1, "lon": 101.1},
                    ],
                    "tags": {"highway": "primary", "ref": "36"},
                },
                {
                    "province": "Rayong",
                    "osm_id": 1,
                    "highway_type": "secondary",
                    "node_ids": [],
                    "geometry": [],
                    "tags": {"highway": "secondary", "name": "Road 2"},
                },
            ],
            expected_highway_types=["primary", "secondary"],
            target_provinces=["Rayong"],
        )

        self.assertFalse(report["quality_pass"])
        self.assertEqual(report["total_records"], 2)
        self.assertEqual(report["duplicate_osm_id_count"], 1)
        self.assertEqual(report["topology"]["geometry_coverage_pct"], 50.0)
        self.assertEqual(report["topology"]["node_ids_coverage_pct"], 50.0)
        self.assertEqual(report["missing_raw_contract_counts"]["fetched_at"], 2)
        self.assertEqual(report["missing_tag_report"]["name"]["missing_count"], 1)
        self.assertEqual(report["missing_tag_report"]["surface"]["missing_count"], 2)

    def test_fetch_tile_failure_writes_marker_and_returns_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("scrapers.road_analysis._tile_max_split_depth", return_value=0):
                with patch(
                    "scrapers.road_analysis._request_overpass",
                    side_effect=RuntimeError("endpoint failed"),
                ):
                    records = _fetch_tile_with_cache(
                        "Rayong",
                        "local",
                        "residential",
                        (101.0, 12.5, 101.1, 12.6),
                        temp_dir,
                        "local_residential_tile_001",
                    )

            failed_path = Path(temp_dir) / "rayong_local_residential_tile_001.failed.json"
            failed_exists = failed_path.exists()

        self.assertEqual(records, [])
        self.assertTrue(failed_exists)


if __name__ == "__main__":
    unittest.main()
