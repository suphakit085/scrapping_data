import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.amenities import scrape_amenities
from utils.data_cleaner import clean_landmarks
from utils.geo_boundaries import (
    prompt_admin_areas,
    prompt_parallel_workers,
    prompt_resume_or_fresh,
)


def main():
    print("========================================")
    print("Starting Amenities-Only Pipeline")
    print("========================================")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    raw_path = os.path.abspath(os.path.join(script_dir, "data/raw/amenities_raw.json"))
    clean_path = os.path.abspath(os.path.join(script_dir, "data/processed/amenities_clean.csv"))
    temp_amenities_dir = os.path.abspath(os.path.join(script_dir, "data/raw/temp_amenities"))

    prompt_resume_or_fresh("Amenities Pipeline", temp_amenities_dir)
    extract_admin_areas = prompt_admin_areas("Amenities Pipeline")
    parallel_workers = prompt_parallel_workers("Amenities", default_workers=3)

    print("\n[1/2] Scraping Amenities...")
    scrape_amenities(
        raw_path,
        parallel_workers=parallel_workers,
        extract_admin_areas=extract_admin_areas,
    )

    print("\n[2/2] Cleaning and Deduplicating...")
    clean_landmarks(raw_path, clean_path)

    print("\n========================================")
    print("Done! Clean amenities saved to:", clean_path)


if __name__ == "__main__":
    main()
