import argparse
import os
import sys

from utils.google_road_enrichment import build_google_road_enrichment_outputs


try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience
    load_dotenv = None


if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Enrich unnamed roads with Google reverse-geocoded route names."
    )
    parser.add_argument(
        "--roads-path",
        default="data/processed/roads.csv",
        help="Input roads CSV path.",
    )
    parser.add_argument(
        "--raw-roads-path",
        default="data/raw/roads_raw.json",
        help="Raw road JSON path used for long-segment midpoint lookup.",
    )
    parser.add_argument(
        "--output-path",
        default="data/processed/roads_enriched.csv",
        help="Output enriched CSV path.",
    )
    parser.add_argument(
        "--cache-path",
        default="data/raw/google_road_name_cache.json",
        help="Cache JSON path for Google lookup results.",
    )
    parser.add_argument(
        "--include-with-ref",
        action="store_true",
        help="Also enrich unnamed roads that already have road_ref.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write output and statuses without calling Google APIs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum eligible Google lookups to run. Useful for pilot runs.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.1,
        help="Delay after each uncached Google lookup.",
    )
    parser.add_argument(
        "--language",
        default="th",
        help="Google Geocoding response language.",
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=15,
        help="Google request timeout in seconds.",
    )
    parser.add_argument(
        "--cache-flush-interval",
        type=int,
        default=25,
        help="Save cache after this many new successful/non-error lookups.",
    )
    return parser.parse_args()


def main():
    if load_dotenv:
        load_dotenv()

    args = parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    result = build_google_road_enrichment_outputs(
        roads_path=os.path.join(script_dir, args.roads_path),
        raw_roads_path=os.path.join(script_dir, args.raw_roads_path),
        output_path=os.path.join(script_dir, args.output_path),
        cache_path=os.path.join(script_dir, args.cache_path),
        api_key=os.environ.get("GOOGLE_MAPS_API_KEY"),
        include_with_ref=args.include_with_ref,
        dry_run=args.dry_run,
        limit=args.limit,
        sleep_seconds=args.sleep_seconds,
        language=args.language,
        request_timeout=args.request_timeout,
        cache_flush_interval=args.cache_flush_interval,
    )

    print(f"[Success] Google road enrichment output saved to {result['output_path']}")
    print(f"[Summary] rows={result['rows']}, selected_lookups={result['lookups_selected']}")
    print(
        f"[Summary] cache_hits={result['cache_hits']}, "
        f"cache_updates={result['cache_updates']}, "
        f"cache_normalizations={result['cache_normalizations']}, "
        f"cache={result['cache_path']}"
    )
    print("[Summary] status_counts:")
    for status, count in result["status_counts"].items():
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
