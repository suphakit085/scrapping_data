# Agent Notes for `ai_web_scrpping`

## What actually runs
- Primary entrypoints from repo root: `python main.py` (full pipeline) and `python run_zones_only.py` (landmarks + zone pipeline only).
- Avoid running scraper files via their `if __name__ == "__main__"` blocks (for example `python scrapers/landmarks.py`): many use `../data/...` paths that resolve incorrectly when run from the repo root.

## Command behavior and order-sensitive flow
- `main.py` runs this sequence: scrape bank loans + property trends + landmarks + Google Maps sync -> clean CSVs -> zone analysis -> S3 upload.
- `run_zones_only.py` does **not** scrape Baania/LivingInsider/DotProperty; it expects raw trends files to already exist before merge/zone steps.
- Google Maps sync is in-place in both pipelines: `scrape_google_maps_sync(raw_landmarks_path, raw_landmarks_path)` overwrites `data/raw/landmarks_raw.json` after enrichment.
- Both pipelines run a processed-data quality gate before success (or before S3 upload in `main.py`); failures raise and stop the flow.

## External prerequisites that are easy to miss
- Python env in repo uses Python 3.13 (`venv/pyvenv.cfg`).
- Playwright is required by multiple scrapers (`google_maps_sync`, `livinginsider_trends`, `baania_trends`); if browser binaries are missing, run `python -m playwright install chromium`.
- Bank loan scraper requires `BOT_API_KEY` in `.env`; without it, bank loan raw output will be empty.
- S3 upload in `main.py` is wired to placeholder bucket `your-target-bucket-name`; update before expecting successful uploads.

## Data contracts and key outputs
- Raw JSON outputs land in `data/raw/`; cleaned/merged CSV outputs land in `data/processed/`.
- Province-specific Layer 2 discovery seeds live at `data/raw/local_iconic_targets.json`; `scrapers/google_maps_sync.py` auto-loads and appends them during sync/discovery.
- Zone analysis (`utils/zone_analyzer.py`) uses Layer 1 anchors from `landmarks_clean.csv` when available, but still searches nearby POIs from raw landmarks JSON.
- Canonical property trends output is `data/processed/property_trends.csv` (from `utils/property_trends_merger.py`) for both pipelines.

## Repo hygiene gotchas
- There is no root `.gitignore` right now; do not assume generated files are ignored.
- This repo currently contains tracked `__pycache__` artifacts in git status; avoid broad cleanup/deletion unless explicitly requested.
