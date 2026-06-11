import csv
import heapq
import json
import math
import os
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from numbers import Integral

from shapely.geometry import LineString, Point, mapping
from shapely.strtree import STRtree

from utils.geo_boundaries import normalize_province_name


PROPERTY_REQUIRED_FIELDNAMES = ["property_id", "chanod_no", "province", "lat", "lon"]
PROPERTY_OPTIONAL_FIELDNAMES = ["source_id"]
PROPERTY_FIELD_ALIASES = {
    "property_id": ["property_id", "parcel_key", "id", "objectid"],
    "source_id": ["source_id", "id"],
    "chanod_no": ["chanod_no", "เลขโฉนด", "เลขที่ค้นหา", "deed_no"],
    "province": ["province", "province_en", "จังหวัด"],
    "lat": ["lat", "latitude", "shape_y"],
    "lon": ["lon", "lng", "longitude", "shape_x"],
}

LOCAL_HIGHWAY_TYPES = {"residential", "unclassified", "service"}
MAJOR_HIGHWAY_TYPES = {"trunk", "primary", "secondary", "tertiary"}
MAJOR_PRIORITY = {"trunk": 0, "primary": 1, "secondary": 2, "tertiary": 3}

DEFAULT_MAX_SNAP_DISTANCE_M = 500.0
DEFAULT_DIRECT_MAJOR_DISTANCE_M = 30.0

PROPERTY_ROAD_ACCESS_FIELDNAMES = [
    "property_id",
    "source_id",
    "chanod_no",
    "province",
    "home_lat",
    "home_lon",
    "snap_distance_m",
    "nearest_local_road_osm_id",
    "nearest_local_road_display_name",
    "soi_mouth_lat",
    "soi_mouth_lon",
    "major_road_osm_id",
    "major_road_display_name",
    "major_highway_type",
    "distance_home_to_soi_mouth_m",
    "routing_status",
    "confidence",
]

_LAT_M = 111_320.0


@dataclass(frozen=True)
class RoadSegment:
    index: int
    start_node: str
    end_node: str
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    distance_m: float
    osm_id: str
    highway_type: str
    road_display_name: str
    line: LineString

    @property
    def is_local(self):
        return self.highway_type in LOCAL_HIGHWAY_TYPES

    @property
    def is_major(self):
        return self.highway_type in MAJOR_HIGHWAY_TYPES


@dataclass(frozen=True)
class RoadEdge:
    to_node: str
    distance_m: float
    segment: RoadSegment


@dataclass(frozen=True)
class SegmentSnap:
    segment: RoadSegment
    snap_lat: float
    snap_lon: float
    snap_distance_m: float
    start_distance_m: float
    end_distance_m: float


@dataclass(frozen=True)
class PathResult:
    distance_m: float
    exit_node: str
    major_segment: RoadSegment
    path_nodes: tuple


def _ensure_parent_dir(path):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _read_csv(path, limit=None):
    if not os.path.exists(path):
        return [], []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(row)
            if limit is not None and len(rows) >= limit:
                break
        return list(reader.fieldnames or []), rows


def _write_csv(path, fieldnames, rows):
    _ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _load_json_list(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_meters(value):
    if value is None:
        return ""
    return f"{float(value):.1f}"


def _format_coord(value):
    if value is None:
        return ""
    return f"{float(value):.7f}"


def _haversine_m(lat1, lon1, lat2, lon2):
    radius = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))


def _lon_m_for_lat(lat):
    return _LAT_M * max(math.cos(math.radians(lat)), 0.01)


def _project_point_to_segment(lat, lon, segment):
    ref_lat = (lat + segment.start_lat + segment.end_lat) / 3.0
    lon_m = _lon_m_for_lat(ref_lat)

    ax = 0.0
    ay = 0.0
    bx = (segment.end_lon - segment.start_lon) * lon_m
    by = (segment.end_lat - segment.start_lat) * _LAT_M
    px = (lon - segment.start_lon) * lon_m
    py = (lat - segment.start_lat) * _LAT_M

    dx = bx - ax
    dy = by - ay
    denom = (dx * dx) + (dy * dy)
    t = 0.0 if denom <= 0 else ((px * dx) + (py * dy)) / denom
    t = max(0.0, min(1.0, t))

    snap_lat = segment.start_lat + ((segment.end_lat - segment.start_lat) * t)
    snap_lon = segment.start_lon + ((segment.end_lon - segment.start_lon) * t)
    snap_distance_m = _haversine_m(lat, lon, snap_lat, snap_lon)
    start_distance_m = _haversine_m(segment.start_lat, segment.start_lon, snap_lat, snap_lon)
    end_distance_m = _haversine_m(snap_lat, snap_lon, segment.end_lat, segment.end_lon)

    return SegmentSnap(
        segment=segment,
        snap_lat=snap_lat,
        snap_lon=snap_lon,
        snap_distance_m=snap_distance_m,
        start_distance_m=start_distance_m,
        end_distance_m=end_distance_m,
    )


def _fallback_road_display_name(record):
    road_name = str(record.get("road_name") or "").strip()
    road_ref = str(record.get("road_ref") or "").strip()
    osm_id = str(record.get("osm_id") or "").strip()

    if road_name and not road_name.startswith("unnamed:"):
        return road_name
    if road_ref:
        return f"Road {road_ref}"
    return road_name or f"unnamed:{osm_id}"


def _load_road_display_lookup(path):
    _, rows = _read_csv(path)
    lookup = {}
    for row in rows:
        osm_id = str(row.get("osm_id") or "").strip()
        display_name = str(row.get("road_display_name") or "").strip()
        if osm_id and display_name:
            lookup[osm_id] = display_name
    return lookup


def _geometry_point(point):
    lat = _to_float((point or {}).get("lat"))
    lon = _to_float((point or {}).get("lon"))
    if lat is None or lon is None:
        return None
    return lat, lon


def _tree_query_indices(tree, geometry, index_by_geometry_id):
    if tree is None:
        return []

    matches = tree.query(geometry)
    indices = []
    for match in matches:
        if isinstance(match, Integral):
            indices.append(int(match))
            continue
        index = index_by_geometry_id.get(id(match))
        if index is not None:
            indices.append(index)
    return indices


class RoadAccessGraph:
    def __init__(self, province, raw_records, road_display_lookup=None):
        self.province = normalize_province_name(province)
        self.nodes = {}
        self.adjacency = defaultdict(list)
        self.local_segments = []
        self.major_segments = []
        self.major_nodes = set()
        self.major_segments_by_node = defaultdict(list)
        self.skipped_records = 0

        road_display_lookup = road_display_lookup or {}
        for record in raw_records:
            self._add_record(record, road_display_lookup)

        self._local_tree, self._local_geometry_index = self._build_tree(self.local_segments)
        self._major_tree, self._major_geometry_index = self._build_tree(self.major_segments)

    @property
    def segment_counts(self):
        return {
            "local_segments": len(self.local_segments),
            "major_segments": len(self.major_segments),
            "nodes": len(self.nodes),
        }

    def _add_record(self, record, road_display_lookup):
        highway_type = str(record.get("highway_type") or "").strip()
        if highway_type not in LOCAL_HIGHWAY_TYPES and highway_type not in MAJOR_HIGHWAY_TYPES:
            return

        node_ids = [str(node_id) for node_id in (record.get("node_ids") or [])]
        geometry = record.get("geometry") or []
        if len(node_ids) < 2 or len(node_ids) != len(geometry):
            self.skipped_records += 1
            return

        points = [_geometry_point(point) for point in geometry]
        if any(point is None for point in points):
            self.skipped_records += 1
            return

        osm_id = str(record.get("osm_id") or "").strip()
        road_display_name = road_display_lookup.get(osm_id) or _fallback_road_display_name(record)

        for index in range(len(node_ids) - 1):
            start_node = node_ids[index]
            end_node = node_ids[index + 1]
            if start_node == end_node:
                continue

            start_lat, start_lon = points[index]
            end_lat, end_lon = points[index + 1]
            distance_m = _haversine_m(start_lat, start_lon, end_lat, end_lon)
            if distance_m <= 0:
                continue

            self.nodes[start_node] = {"lat": start_lat, "lon": start_lon}
            self.nodes[end_node] = {"lat": end_lat, "lon": end_lon}

            segment = RoadSegment(
                index=len(self.local_segments) + len(self.major_segments),
                start_node=start_node,
                end_node=end_node,
                start_lat=start_lat,
                start_lon=start_lon,
                end_lat=end_lat,
                end_lon=end_lon,
                distance_m=distance_m,
                osm_id=osm_id,
                highway_type=highway_type,
                road_display_name=road_display_name,
                line=LineString([(start_lon, start_lat), (end_lon, end_lat)]),
            )

            self.adjacency[start_node].append(RoadEdge(end_node, distance_m, segment))
            self.adjacency[end_node].append(RoadEdge(start_node, distance_m, segment))

            if segment.is_local:
                self.local_segments.append(segment)
            elif segment.is_major:
                self.major_segments.append(segment)
                self.major_nodes.add(start_node)
                self.major_nodes.add(end_node)
                self.major_segments_by_node[start_node].append(segment)
                self.major_segments_by_node[end_node].append(segment)

    def _build_tree(self, segments):
        if not segments:
            return None, {}
        geometries = [segment.line for segment in segments]
        return STRtree(geometries), {id(geometry): index for index, geometry in enumerate(geometries)}

    def nearest_snap(self, lat, lon, road_type="local", max_distance_m=None):
        segments = self.local_segments if road_type == "local" else self.major_segments
        tree = self._local_tree if road_type == "local" else self._major_tree
        geometry_index = (
            self._local_geometry_index if road_type == "local" else self._major_geometry_index
        )
        if not segments:
            return None

        point = Point(lon, lat)
        if max_distance_m is None:
            candidate_indices = self._nearest_indices(tree, point, geometry_index, segments)
        else:
            buffer_deg = max(float(max_distance_m), 1.0) / _LAT_M
            candidate_indices = _tree_query_indices(tree, point.buffer(buffer_deg), geometry_index)
            if not candidate_indices:
                candidate_indices = self._nearest_indices(tree, point, geometry_index, segments)

        best = None
        for index in candidate_indices:
            snap = _project_point_to_segment(lat, lon, segments[index])
            if best is None or snap.snap_distance_m < best.snap_distance_m:
                best = snap

        if best and max_distance_m is not None and best.snap_distance_m > max_distance_m:
            return None
        return best

    def _nearest_indices(self, tree, point, geometry_index, segments):
        if tree is None:
            return []
        try:
            nearest = tree.nearest(point)
        except Exception:
            return list(range(len(segments)))

        if isinstance(nearest, Integral):
            return [int(nearest)]

        index = geometry_index.get(id(nearest))
        if index is not None:
            return [index]

        return list(range(len(segments)))

    def shortest_path_to_major(self, snap):
        virtual_node = "__property_snap__"
        virtual_edges = [
            RoadEdge(snap.segment.start_node, snap.start_distance_m, snap.segment),
            RoadEdge(snap.segment.end_node, snap.end_distance_m, snap.segment),
        ]

        distances = {virtual_node: 0.0}
        previous = {}
        queue = [(0.0, virtual_node)]

        while queue:
            current_distance, node = heapq.heappop(queue)
            if current_distance != distances.get(node):
                continue

            if node != virtual_node and node in self.major_nodes:
                major_segment = self._select_major_segment(node)
                if major_segment:
                    return PathResult(
                        distance_m=current_distance,
                        exit_node=node,
                        major_segment=major_segment,
                        path_nodes=self._reconstruct_path(previous, node),
                    )

            edges = virtual_edges if node == virtual_node else self.adjacency.get(node, [])
            for edge in edges:
                new_distance = current_distance + edge.distance_m
                if new_distance < distances.get(edge.to_node, float("inf")):
                    distances[edge.to_node] = new_distance
                    previous[edge.to_node] = node
                    heapq.heappush(queue, (new_distance, edge.to_node))

        return None

    def _select_major_segment(self, node):
        segments = self.major_segments_by_node.get(node) or []
        if not segments:
            return None
        return sorted(
            segments,
            key=lambda segment: (
                MAJOR_PRIORITY.get(segment.highway_type, 99),
                segment.road_display_name,
                segment.osm_id,
            ),
        )[0]

    def _reconstruct_path(self, previous, node):
        nodes = [node]
        while node in previous:
            node = previous[node]
            if node != "__property_snap__":
                nodes.append(node)
        nodes.reverse()
        return tuple(nodes)


def build_road_access_graph(raw_records, province="", road_display_lookup=None):
    return RoadAccessGraph(province, raw_records, road_display_lookup=road_display_lookup)


def _base_output_row(property_row):
    return {
        "property_id": property_row.get("property_id", ""),
        "source_id": property_row.get("source_id", ""),
        "chanod_no": property_row.get("chanod_no", ""),
        "province": normalize_province_name(property_row.get("province")),
        "home_lat": str(property_row.get("lat") or "").strip(),
        "home_lon": str(property_row.get("lon") or "").strip(),
        "snap_distance_m": "",
        "nearest_local_road_osm_id": "",
        "nearest_local_road_display_name": "",
        "soi_mouth_lat": "",
        "soi_mouth_lon": "",
        "major_road_osm_id": "",
        "major_road_display_name": "",
        "major_highway_type": "",
        "distance_home_to_soi_mouth_m": "",
        "routing_status": "",
        "confidence": "",
        "_route_geometry": [],
    }


def _confidence_for_snap(snap_distance_m, status):
    if status not in {"routed", "already_on_major"}:
        return "low"
    if snap_distance_m <= 50:
        return "high"
    return "medium"


def _route_geometry(home_lat, home_lon, snap, graph, path_result=None):
    coordinates = [[home_lon, home_lat], [snap.snap_lon, snap.snap_lat]]
    if path_result:
        for node_id in path_result.path_nodes:
            point = graph.nodes.get(node_id)
            if point:
                coordinates.append([point["lon"], point["lat"]])

    deduped = []
    for coordinate in coordinates:
        if not deduped or coordinate != deduped[-1]:
            deduped.append(coordinate)
    return deduped


def route_property_row(
    property_row,
    graph,
    max_snap_distance_m=DEFAULT_MAX_SNAP_DISTANCE_M,
    direct_major_distance_m=DEFAULT_DIRECT_MAJOR_DISTANCE_M,
):
    property_row = normalize_property_row(property_row)
    output = _base_output_row(property_row)
    lat = _to_float(property_row.get("lat"))
    lon = _to_float(property_row.get("lon"))

    if lat is None or lon is None:
        output["routing_status"] = "invalid_coordinates"
        output["confidence"] = "low"
        return output

    output["home_lat"] = _format_coord(lat)
    output["home_lon"] = _format_coord(lon)

    if graph is None or not graph.nodes:
        output["routing_status"] = "no_road_graph"
        output["confidence"] = "low"
        return output

    local_snap = graph.nearest_snap(lat, lon, "local", max_distance_m=max_snap_distance_m)
    major_snap = graph.nearest_snap(
        lat,
        lon,
        "major",
        max_distance_m=max(max_snap_distance_m, direct_major_distance_m),
    )

    if (
        major_snap
        and major_snap.snap_distance_m <= direct_major_distance_m
        and (not local_snap or major_snap.snap_distance_m <= local_snap.snap_distance_m)
    ):
        segment = major_snap.segment
        status = "already_on_major"
        output.update(
            {
                "snap_distance_m": _format_meters(major_snap.snap_distance_m),
                "soi_mouth_lat": _format_coord(major_snap.snap_lat),
                "soi_mouth_lon": _format_coord(major_snap.snap_lon),
                "major_road_osm_id": segment.osm_id,
                "major_road_display_name": segment.road_display_name,
                "major_highway_type": segment.highway_type,
                "distance_home_to_soi_mouth_m": _format_meters(major_snap.snap_distance_m),
                "routing_status": status,
                "confidence": _confidence_for_snap(major_snap.snap_distance_m, status),
                "_route_geometry": _route_geometry(lat, lon, major_snap, graph),
            }
        )
        return output

    if not local_snap:
        if major_snap:
            segment = major_snap.segment
            status = "already_on_major"
            output.update(
                {
                    "snap_distance_m": _format_meters(major_snap.snap_distance_m),
                    "soi_mouth_lat": _format_coord(major_snap.snap_lat),
                    "soi_mouth_lon": _format_coord(major_snap.snap_lon),
                    "major_road_osm_id": segment.osm_id,
                    "major_road_display_name": segment.road_display_name,
                    "major_highway_type": segment.highway_type,
                    "distance_home_to_soi_mouth_m": _format_meters(major_snap.snap_distance_m),
                    "routing_status": status,
                    "confidence": "medium",
                    "_route_geometry": _route_geometry(lat, lon, major_snap, graph),
                }
            )
            return output

        output["routing_status"] = "no_nearby_local_road"
        output["confidence"] = "low"
        return output

    output.update(
        {
            "snap_distance_m": _format_meters(local_snap.snap_distance_m),
            "nearest_local_road_osm_id": local_snap.segment.osm_id,
            "nearest_local_road_display_name": local_snap.segment.road_display_name,
        }
    )

    path_result = graph.shortest_path_to_major(local_snap)
    if not path_result:
        output["routing_status"] = "no_major_reachable"
        output["confidence"] = "low"
        output["_route_geometry"] = _route_geometry(lat, lon, local_snap, graph)
        return output

    exit_point = graph.nodes.get(path_result.exit_node, {})
    total_distance_m = local_snap.snap_distance_m + path_result.distance_m
    status = "routed"
    output.update(
        {
            "soi_mouth_lat": _format_coord(exit_point.get("lat")),
            "soi_mouth_lon": _format_coord(exit_point.get("lon")),
            "major_road_osm_id": path_result.major_segment.osm_id,
            "major_road_display_name": path_result.major_segment.road_display_name,
            "major_highway_type": path_result.major_segment.highway_type,
            "distance_home_to_soi_mouth_m": _format_meters(total_distance_m),
            "routing_status": status,
            "confidence": _confidence_for_snap(local_snap.snap_distance_m, status),
            "_route_geometry": _route_geometry(lat, lon, local_snap, graph, path_result),
        }
    )
    return output


def _validate_property_headers(fieldnames):
    missing = [
        field
        for field in PROPERTY_REQUIRED_FIELDNAMES
        if not _field_alias(fieldnames, field)
    ]
    if missing:
        supported = {
            field: PROPERTY_FIELD_ALIASES[field]
            for field in PROPERTY_REQUIRED_FIELDNAMES
        }
        raise ValueError(
            "property_locations.csv missing required logical headers: "
            f"{', '.join(missing)}. Supported aliases: {supported}"
        )


def _field_alias(fieldnames, canonical_field):
    field_set = set(fieldnames or [])
    for field in PROPERTY_FIELD_ALIASES[canonical_field]:
        if field in field_set:
            return field
    return ""


def _first_value(row, aliases):
    for field in aliases:
        value = row.get(field)
        if str(value or "").strip() != "":
            return value
    return ""


def normalize_property_row(row):
    normalized = dict(row or {})
    for canonical_field in PROPERTY_REQUIRED_FIELDNAMES:
        normalized[canonical_field] = _first_value(
            normalized,
            PROPERTY_FIELD_ALIASES[canonical_field],
        )
    for canonical_field in PROPERTY_OPTIONAL_FIELDNAMES:
        normalized[canonical_field] = _first_value(
            normalized,
            PROPERTY_FIELD_ALIASES[canonical_field],
        )
    normalized["province"] = normalize_province_name(normalized.get("province"))
    return normalized


def _group_raw_roads_by_province(raw_records, target_provinces):
    target_provinces = {normalize_province_name(province) for province in target_provinces if province}
    grouped = defaultdict(list)
    for record in raw_records:
        province = normalize_province_name(record.get("province"))
        if province in target_provinces:
            grouped[province].append(record)
    return grouped


def _write_geojson(path, route_rows):
    path = os.path.abspath(os.path.normpath(path))
    _ensure_parent_dir(path)
    temp_path = f"{path}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    feature_count = 0

    with open(temp_path, "w", encoding="utf-8") as f:
        f.write('{"type":"FeatureCollection","features":[\n')
        first = True
        for row in route_rows:
            coordinates = row.get("_route_geometry") or []
            if len(coordinates) < 2:
                continue
            properties = {
                field: row.get(field, "")
                for field in PROPERTY_ROAD_ACCESS_FIELDNAMES
                if field not in {"home_lat", "home_lon"}
            }
            feature = {
                "type": "Feature",
                "properties": properties,
                "geometry": mapping(LineString(coordinates)),
            }
            if not first:
                f.write(",\n")
            json.dump(feature, f, ensure_ascii=False, separators=(",", ":"))
            first = False
            feature_count += 1
        f.write("\n]}\n")

    last_error = None
    for attempt in range(10):
        try:
            os.replace(temp_path, path)
            return feature_count
        except (OSError, PermissionError) as exc:
            last_error = exc
            time.sleep(0.2 * (attempt + 1))

    fallback_path = f"{path}.pending-{uuid.uuid4().hex}.geojson"
    try:
        os.replace(temp_path, fallback_path)
    except OSError:
        fallback_path = temp_path
    print(
        "[Warning] Could not replace route GeoJSON because Windows denied access. "
        f"Latest snapshot left at {fallback_path}. Error: {last_error}"
    )
    return feature_count

def build_property_road_access_outputs(
    properties_path="data/raw/property_locations.csv",
    raw_roads_path="data/raw/roads_raw.json",
    roads_final_path="data/processed/roads_final.csv",
    output_path="data/processed/property_road_access.csv",
    geojson_path=None,
    max_snap_distance_m=DEFAULT_MAX_SNAP_DISTANCE_M,
    direct_major_distance_m=DEFAULT_DIRECT_MAJOR_DISTANCE_M,
    limit=None,
):
    property_fieldnames, property_rows = _read_csv(properties_path, limit=limit)
    if not property_rows:
        raise ValueError(f"No property rows found: {properties_path}")
    _validate_property_headers(property_fieldnames)
    property_rows = [normalize_property_row(row) for row in property_rows]

    target_provinces = {
        normalize_province_name(row.get("province"))
        for row in property_rows
        if normalize_province_name(row.get("province"))
    }
    raw_records = _load_json_list(raw_roads_path)
    if not raw_records:
        raise ValueError(f"No road rows found: {raw_roads_path}")

    road_display_lookup = _load_road_display_lookup(roads_final_path)
    roads_by_province = _group_raw_roads_by_province(raw_records, target_provinces)
    graphs = {
        province: build_road_access_graph(
            roads_by_province.get(province, []),
            province=province,
            road_display_lookup=road_display_lookup,
        )
        for province in target_provinces
    }

    route_rows = []
    for row in property_rows:
        province = normalize_province_name(row.get("province"))
        route_rows.append(
            route_property_row(
                row,
                graphs.get(province),
                max_snap_distance_m=max_snap_distance_m,
                direct_major_distance_m=direct_major_distance_m,
            )
        )

    _write_csv(output_path, PROPERTY_ROAD_ACCESS_FIELDNAMES, route_rows)
    if geojson_path:
        _write_geojson(geojson_path, route_rows)

    status_counts = Counter(row.get("routing_status", "unknown") for row in route_rows)
    graph_counts = {
        province: graph.segment_counts
        for province, graph in sorted(graphs.items())
    }

    return {
        "rows": len(route_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "graph_counts": graph_counts,
        "output_path": output_path,
        "geojson_path": geojson_path or "",
    }
