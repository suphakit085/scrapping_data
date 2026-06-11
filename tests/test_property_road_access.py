import csv
import json
import tempfile
import unittest
from pathlib import Path

from utils.property_road_access import (
    build_property_road_access_outputs,
    build_road_access_graph,
    route_property_row,
)


def road(osm_id, highway_type, node_ids, points, name=""):
    return {
        "province": "Rayong",
        "osm_id": str(osm_id),
        "road_name": name or f"Road {osm_id}",
        "road_ref": "",
        "highway_type": highway_type,
        "node_ids": node_ids,
        "geometry": [{"lat": lat, "lon": lon} for lat, lon in points],
        "tags": {"highway": highway_type},
    }


class PropertyRoadAccessTests(unittest.TestCase):
    def test_two_soi_mouths_chooses_shortest_network_path(self):
        graph = build_road_access_graph(
            [
                road("100", "residential", ["west", "mid", "east"], [(14.0, 102.0), (14.0, 102.01), (14.0, 102.02)]),
                road("200", "primary", ["major_w", "west"], [(14.0, 101.99), (14.0, 102.0)], "West Major"),
                road("300", "primary", ["east", "major_e"], [(14.0, 102.02), (14.0, 102.03)], "East Major"),
            ],
            province="Rayong",
        )

        result = route_property_row(
            {
                "property_id": "p1",
                "chanod_no": "c1",
                "province": "Rayong",
                "lat": "14.0001",
                "lon": "102.016",
            },
            graph,
        )

        self.assertEqual(result["routing_status"], "routed")
        self.assertEqual(result["major_road_osm_id"], "300")
        self.assertEqual(result["major_road_display_name"], "East Major")
        self.assertLess(float(result["distance_home_to_soi_mouth_m"]), 500)

    def test_dead_end_routes_back_to_only_major_exit(self):
        graph = build_road_access_graph(
            [
                road("100", "residential", ["exit", "dead"], [(14.0, 102.0), (14.0, 102.01)]),
                road("200", "secondary", ["major", "exit"], [(14.0, 101.99), (14.0, 102.0)], "Secondary Road"),
            ],
            province="Rayong",
        )

        result = route_property_row(
            {
                "property_id": "p1",
                "chanod_no": "c1",
                "province": "Rayong",
                "lat": "14.0001",
                "lon": "102.009",
            },
            graph,
        )

        self.assertEqual(result["routing_status"], "routed")
        self.assertEqual(result["major_road_osm_id"], "200")
        self.assertAlmostEqual(float(result["soi_mouth_lon"]), 102.0, places=5)

    def test_property_on_major_is_already_on_major(self):
        graph = build_road_access_graph(
            [
                road("200", "primary", ["a", "b"], [(14.0, 102.0), (14.0, 102.02)], "Primary Road"),
            ],
            province="Rayong",
        )

        result = route_property_row(
            {
                "property_id": "p1",
                "chanod_no": "c1",
                "province": "Rayong",
                "lat": "14.0",
                "lon": "102.01",
            },
            graph,
        )

        self.assertEqual(result["routing_status"], "already_on_major")
        self.assertEqual(result["major_highway_type"], "primary")
        self.assertEqual(float(result["distance_home_to_soi_mouth_m"]), 0.0)

    def test_local_road_without_major_is_not_reachable(self):
        graph = build_road_access_graph(
            [
                road("100", "residential", ["a", "b"], [(14.0, 102.0), (14.0, 102.01)]),
            ],
            province="Rayong",
        )

        result = route_property_row(
            {
                "property_id": "p1",
                "chanod_no": "c1",
                "province": "Rayong",
                "lat": "14.0001",
                "lon": "102.005",
            },
            graph,
        )

        self.assertEqual(result["routing_status"], "no_major_reachable")

    def test_motorway_is_not_counted_as_major_exit(self):
        graph = build_road_access_graph(
            [
                road("100", "residential", ["a", "b"], [(14.0, 102.0), (14.0, 102.01)]),
                road("999", "motorway", ["b", "c"], [(14.0, 102.01), (14.0, 102.02)], "Motorway"),
            ],
            province="Rayong",
        )

        result = route_property_row(
            {
                "property_id": "p1",
                "chanod_no": "c1",
                "province": "Rayong",
                "lat": "14.0",
                "lon": "102.009",
            },
            graph,
        )

        self.assertEqual(result["routing_status"], "no_major_reachable")
        self.assertEqual(result["major_road_osm_id"], "")

    def test_build_outputs_writes_expected_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            properties_path = root / "property_locations.csv"
            raw_roads_path = root / "roads_raw.json"
            roads_final_path = root / "roads_final.csv"
            output_path = root / "property_road_access.csv"

            with open(properties_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["property_id", "id", "chanod_no", "province", "lat", "lon"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "property_id": "p1",
                        "id": "SRC1",
                        "chanod_no": "c1",
                        "province": "Rayong",
                        "lat": "14.0001",
                        "lon": "102.009",
                    }
                )

            with open(raw_roads_path, "w", encoding="utf-8") as f:
                json.dump(
                    [
                        road("100", "residential", ["exit", "home"], [(14.0, 102.0), (14.0, 102.01)]),
                        road("200", "primary", ["major", "exit"], [(14.0, 101.99), (14.0, 102.0)]),
                    ],
                    f,
                )

            with open(roads_final_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["osm_id", "road_display_name"])
                writer.writeheader()
                writer.writerow({"osm_id": "200", "road_display_name": "ถนนใหญ่"})

            result = build_property_road_access_outputs(
                properties_path=str(properties_path),
                raw_roads_path=str(raw_roads_path),
                roads_final_path=str(roads_final_path),
                output_path=str(output_path),
            )

            with open(output_path, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(result["rows"], 1)
        self.assertEqual(rows[0]["property_id"], "p1")
        self.assertEqual(rows[0]["source_id"], "SRC1")
        self.assertEqual(rows[0]["routing_status"], "routed")
        self.assertEqual(rows[0]["major_road_display_name"], "ถนนใหญ่")

    def test_build_outputs_accepts_treasury_thai_headers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            properties_path = root / "treasury.csv"
            raw_roads_path = root / "roads_raw.json"
            roads_final_path = root / "roads_final.csv"
            output_path = root / "property_road_access.csv"

            with open(properties_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["parcel_key", "เลขโฉนด", "จังหวัด", "longitude", "latitude"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "parcel_key": "PARCEL_47_POINT|40030000|40037061",
                        "เลขโฉนด": "1",
                        "จังหวัด": "ขอนแก่น",
                        "longitude": "102.009",
                        "latitude": "14.0001",
                    }
                )

            with open(raw_roads_path, "w", encoding="utf-8") as f:
                json.dump(
                    [
                        {
                            **road("100", "residential", ["exit", "home"], [(14.0, 102.0), (14.0, 102.01)]),
                            "province": "Khon Kaen",
                        },
                        {
                            **road("200", "primary", ["major", "exit"], [(14.0, 101.99), (14.0, 102.0)]),
                            "province": "Khon Kaen",
                        },
                    ],
                    f,
                )

            with open(roads_final_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["osm_id", "road_display_name"])
                writer.writeheader()

            result = build_property_road_access_outputs(
                properties_path=str(properties_path),
                raw_roads_path=str(raw_roads_path),
                roads_final_path=str(roads_final_path),
                output_path=str(output_path),
            )

            with open(output_path, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))

        self.assertEqual(result["rows"], 1)
        self.assertEqual(rows[0]["property_id"], "PARCEL_47_POINT|40030000|40037061")
        self.assertEqual(rows[0]["chanod_no"], "1")
        self.assertEqual(rows[0]["province"], "Khon Kaen")
        self.assertEqual(rows[0]["routing_status"], "routed")


if __name__ == "__main__":
    unittest.main()
