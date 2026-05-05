import csv
import os


REQUIRED_PROPERTY_TYPES = {"House", "Condo", "Land", "Townhouse"}


def _read_csv_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def validate_pipeline_outputs(landmarks_path, property_trends_path, zones_path, expected_province_count=10):
    """
    Validate core processed outputs before downstream consumption/upload.
    Returns: (is_valid: bool, messages: list[str])
    """
    messages = []
    ok = True

    paths_to_check = [landmarks_path, zones_path]
    if property_trends_path:
        paths_to_check.append(property_trends_path)

    for path in paths_to_check:
        if not os.path.exists(path):
            ok = False
            messages.append(f"[ERROR] Missing required file: {path}")

    if not ok:
        return ok, messages

    landmarks = _read_csv_rows(landmarks_path)
    zones = _read_csv_rows(zones_path)
    trends = _read_csv_rows(property_trends_path) if property_trends_path and os.path.exists(property_trends_path) else []

    if not landmarks:
        ok = False
        messages.append(f"[ERROR] Empty landmarks file: {landmarks_path}")
    if property_trends_path and not trends:
        ok = False
        messages.append(f"[ERROR] Empty trends file: {property_trends_path}")
    if not zones:
        ok = False
        messages.append(f"[ERROR] Empty zones file: {zones_path}")
    if not ok:
        return ok, messages

    # 1) landmarks: each province must have layer 1/2/3
    layer_by_province = {}
    for r in landmarks:
        prov = (r.get("province") or "").strip()
        layer = str(r.get("layer") or "").strip()
        if not prov or not layer:
            continue
        layer_by_province.setdefault(prov, set()).add(layer)

    if len(layer_by_province) != expected_province_count:
        ok = False
        messages.append(
            f"[ERROR] Landmarks province count={len(layer_by_province)} (expected {expected_province_count})"
        )

    missing_layers = []
    for prov, layers in sorted(layer_by_province.items()):
        required = {"1", "2", "3"}
        if not required.issubset(layers):
            missing_layers.append(f"{prov}: missing {sorted(required - layers)}")
    if missing_layers:
        ok = False
        messages.append("[ERROR] Landmarks layer coverage is incomplete by province")
        messages.extend([f"  - {m}" for m in missing_layers])

    # 2) trends: each province should have all required property types and positive median_price
    if property_trends_path and trends:
        trends_map = {}
        bad_median = 0
        for r in trends:
            prov = (r.get("province") or "").strip()
            ptype = (r.get("property_type") or "").strip()
            median_raw = r.get("median_price")
            if prov and ptype:
                trends_map.setdefault(prov, set()).add(ptype)

            try:
                if float(median_raw) <= 0:
                    bad_median += 1
            except Exception:
                bad_median += 1

        if len(trends_map) != expected_province_count:
            ok = False
            messages.append(
                f"[ERROR] Trends province count={len(trends_map)} (expected {expected_province_count})"
            )

        missing_types = []
        for prov, ptypes in sorted(trends_map.items()):
            if not REQUIRED_PROPERTY_TYPES.issubset(ptypes):
                missing_types.append(f"{prov}: missing {sorted(REQUIRED_PROPERTY_TYPES - ptypes)}")
        if missing_types:
            ok = False
            messages.append("[ERROR] Trends property-type coverage is incomplete by province")
            messages.extend([f"  - {m}" for m in missing_types])

        if bad_median > 0:
            ok = False
            messages.append(f"[ERROR] Trends has {bad_median} row(s) with missing/invalid median_price")

    # 3) zones: rows must match number of layer-1 anchors
    layer1_count = sum(1 for r in landmarks if str(r.get("layer") or "").strip() == "1")
    if len(zones) != layer1_count:
        ok = False
        messages.append(
            f"[ERROR] Zone rows={len(zones)} but layer1 anchors={layer1_count}"
        )

    if ok:
        messages.append("[OK] Data quality checks passed")
        messages.append(f"  - Canonical trends output: {property_trends_path}")

    return ok, messages
