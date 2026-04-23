import requests
from bs4 import BeautifulSoup
import json

def scrape_dotproperty(province="khon-kaen"):
    url = f"https://www.dotproperty.co.th/en/properties-for-sale/{province}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    print(f"Scraping DotProperty for {province}...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # The number of properties is usually in the H1 or a summary tag
            # e.g., "1,234 Properties for sale in Khon Kaen"
            h1 = soup.find('h1')
            title_text = h1.text.strip() if h1 else "Unknown"
            
            # Let's find all listing prices to calculate an average
            price_elements = soup.select('.price')
            prices = []
            for p in price_elements:
                text = p.text.replace('฿', '').replace(',', '').strip()
                try:
                    prices.append(float(text))
                except ValueError:
                    pass
                    
            avg_price = sum(prices) / len(prices) if prices else 0
            
            print(f"Title: {title_text}")
            print(f"Found {len(prices)} listings on the first page.")
            print(f"Average Price on Page 1: {avg_price:,.2f} THB")
            
            return {
                "province": province,
                "title": title_text,
                "sample_size": len(prices),
                "average_price_thb": avg_price
            }
        else:
            print(f"Failed: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scrape_dotproperty("khon-kaen")
