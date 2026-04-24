import sys, json, time
sys.path.insert(0, '.')

from playwright.sync_api import sync_playwright
from scrapers.google_maps_sync import scrape_google_maps_pois, SEARCH_TARGETS

results_summary = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--lang=th-TH,th'])
    context = browser.new_context(
        locale='th-TH',
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': 1280, 'height': 800}
    )
    page = context.new_page()

    province = 'ขอนแก่น'
    print(f'=== Testing Discovery Mode: {province} ===')

    # Test Layer 1 + 2 targets only
    test_targets = [t for t in SEARCH_TARGETS if t['layer'] in (1, 2)][:8]
    for target in test_targets:
        query = target['query']
        print(f"  Searching '{query}'...", end=' ', flush=True)
        pois = scrape_google_maps_pois(province, query, page, max_results=6)
        print(f'{len(pois)} found')
        for poi in pois:
            results_summary.append({
                'layer': target['layer'],
                'query': query,
                'name': poi['name'],
                'lat': poi['lat'],
                'lon': poi['lon']
            })
        time.sleep(1)

    browser.close()

print()
print('=== Discovery Results ===')
for r in results_summary:
    print(f"  [L{r['layer']} | {r['query']}] {r['name']} -> ({r['lat']:.4f}, {r['lon']:.4f})")
print(f'\nTotal: {len(results_summary)} POIs discovered for {province}')
