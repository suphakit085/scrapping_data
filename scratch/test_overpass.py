import requests
import sys
sys.stdout.reconfigure(encoding='utf-8')

area_id = 18934428 + 3600000000  # Khon Kaen Amphoe Mueang
query = '[out:json][timeout:60];area(AREA_ID)->.s;(nwr["amenity"="university"](area.s);nwr["amenity"="hospital"](area.s);nwr["shop"="mall"](area.s););out center tags;'
query = query.replace("AREA_ID", str(area_id))

r = requests.get(
    'https://overpass.kumi.systems/api/interpreter',
    params={'data': query},
    headers={'User-Agent': 'BI-Pipeline/1.0'},
    timeout=60
)
els = r.json().get('elements', [])
print(f'Status: {r.status_code}, POIs found: {len(els)}')
for e in els[:10]:
    tags = e.get('tags', {})
    name = tags.get('name', tags.get('name:en', '(no name)'))
    kind = tags.get('amenity', tags.get('shop', '?'))
    print(f'  [{kind}] {name}')
