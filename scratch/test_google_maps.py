import sys
sys.path.insert(0, '.')
from scrapers.google_maps_sync import scrape_google_maps_pois
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(locale='th-TH')
    page = context.new_page()
    results = scrape_google_maps_pois('ขอนแก่น', '7-Eleven', page, max_results=5)
    browser.close()

print(f'Found {len(results)} results:')
for r in results:
    print(f'  {r["name"]} -> ({r["lat"]}, {r["lon"]})')
