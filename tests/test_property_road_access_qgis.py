import json
import tempfile
import unittest
from pathlib import Path

from utils.property_road_access_qgis import export_property_points_geojson


class PropertyRoadAccessQgisTests(unittest.TestCase):
    def test_export_property_points_geojson_filters_issue_statuses(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "property_road_access.csv"
            output_path = root / "issues.geojson"

            csv_path.write_text(
                "\n".join(
                    [
                        "property_id,chanod_no,province,home_lat,home_lon,routing_status,confidence",
                        "p1,1,Khon Kaen,16.0,102.0,routed,high",
                        "p2,2,Khon Kaen,16.1,102.1,no_nearby_local_road,low",
                        "p3,3,Khon Kaen,16.2,102.2,no_major_reachable,low",
                        "p4,4,Khon Kaen,,102.3,invalid_coordinates,low",
                    ]
                ),
                encoding="utf-8-sig",
            )

            result = export_property_points_geojson(
                csv_path=str(csv_path),
                output_path=str(output_path),
            )
            data = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result["features"], 2)
        self.assertEqual(len(data["features"]), 2)
        self.assertEqual(data["features"][0]["properties"]["property_id"], "p2")
        self.assertEqual(data["features"][1]["geometry"]["coordinates"], [102.2, 16.2])


if __name__ == "__main__":
    unittest.main()
