import requests
import time

NOMINATIM = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "BI-Pipeline/1.0 contact@example.com"}

searches = [
    ("ขอนแก่น",        "Mueang Khon Kaen District, Khon Kaen, Thailand"),
    ("อุบลราชธานี",     "Mueang Ubon Ratchathani District, Ubon Ratchathani, Thailand"),
    ("ประจวบคีรีขันธ์", "Mueang Prachuap Khiri Khan District, Prachuap Khiri Khan, Thailand"),
    ("อุดรธานี",        "Mueang Udon Thani District, Udon Thani, Thailand"),
    ("ระยอง",           "Mueang Rayong District, Rayong, Thailand"),
    ("ชลบุรี",          "Mueang Chon Buri District, Chon Buri, Thailand"),
    ("สุรินทร์",        "Mueang Surin District, Surin, Thailand"),
    ("บุรีรัมย์",       "Mueang Buri Ram District, Buri Ram, Thailand"),
    ("พิษณุโลก",        "Mueang Phitsanulok District, Phitsanulok, Thailand"),
    ("เชียงราย",        "Mueang Chiang Rai District, Chiang Rai, Thailand"),
]

print("Searching for Amphoe Mueang relation IDs via Nominatim...\n")

for thai, query in searches:
    r = requests.get(NOMINATIM, params={
        "q": query,
        "format": "json",
        "limit": 3,
        "addressdetails": 0
    }, headers=HEADERS, timeout=20)
    
    if r.status_code != 200 or not r.text.strip():
        print(f'  {thai}: HTTP {r.status_code} - skipped')
        time.sleep(1)
        continue
    
    results = r.json()
    found = False
    for res in results:
        if res.get("osm_type") == "relation":
            print(f'  {{"name": "{thai}", "relation_id": {res["osm_id"]}}},  # {res.get("display_name","")[:60]}')
            found = True
            break
    if not found:
        for res in results:
            print(f'  {thai}: osm_type={res.get("osm_type")}, id={res.get("osm_id")}, display={res.get("display_name","")[:60]}')
        if not results:
            print(f'  {thai}: NOT FOUND')
    
    time.sleep(1)  # Respect Nominatim rate limit
