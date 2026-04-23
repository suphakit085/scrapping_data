import requests
from bs4 import BeautifulSoup

url = "https://www.dotproperty.co.th/en/properties-for-sale/khon-kaen"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print("Testing DotProperty Request...")
try:
    response = requests.get(url, headers=headers, timeout=15)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('title')
        print(f"Page Title: {title.text if title else 'No title found'}")
        
        # Try to find property count
        count_element = soup.select_one('h1')
        print(f"H1 Element: {count_element.text.strip() if count_element else 'No H1 found'}")
        
        # Save HTML for inspection
        with open("scratch/dotproperty_test.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("Saved HTML to scratch/dotproperty_test.html")
    else:
        print("Request blocked or failed.")
        
except Exception as e:
    print(f"Error: {e}")
