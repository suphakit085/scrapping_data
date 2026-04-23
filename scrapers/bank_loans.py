import json
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

def scrape_bot_api():
    """
    Fetches bank loan rates (MRR, MLR, MOR) from the Bank of Thailand (BOT) API.
    """
    print("Fetching Loan Rates from BOT API...")
    load_dotenv()
    api_key = os.getenv("BOT_API_KEY")
    if not api_key:
        print("Error: BOT_API_KEY not found in .env file.")
        return []

    url = "https://gateway.api.bot.or.th/LoanRate/v2/loan_rate/"
    headers = {
        "Authorization": api_key,
        "accept": "application/json"
    }

    # API limits to 31 days max. We fetch the last 7 days to get the latest active rates.
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    params = {
        "start_period": start_date.strftime("%Y-%m-%d"),
        "end_period": end_date.strftime("%Y-%m-%d")
    }

    data_to_save = []
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        bot_data = response.json()
        
        # Parse the JSON response
        details = bot_data.get("result", {}).get("data", {}).get("data_detail", [])
        
        # Map to keep only the latest date entry for each bank
        latest_rates = {}
        for row in details:
            bank_name = row.get("bank_name_eng", "")
            period = row.get("period", "")
            
            if bank_name not in latest_rates or period > latest_rates[bank_name]["period"]:
                latest_rates[bank_name] = row
                
        # Process all local commercial banks
        for bank_name, row in latest_rates.items():
            bank_type = row.get("bank_type_name_th", "")
            
            # Filter for local commercial banks only (exclude foreign branches which usually don't have home loans)
            if bank_type == "ธนาคารพาณิชย์จดทะเบียนในประเทศ":
                # Use the Thai name for better readability, or English if you prefer
                display_name = row.get("bank_name_th", bank_name)
                
                data_to_save.append({
                    "bank": display_name,
                    "loan_type": "Home Loan (Base Rates)",
                    "interest_rate_yr1_to_3": "N/A (Use Base MRR)",
                    "mrr": f"{row.get('mrr', 'N/A')}%",
                    "mlr": f"{row.get('mlr', 'N/A')}%",
                    "mor": f"{row.get('mor', 'N/A')}%",
                    "last_updated": row.get("period", ""),
                    "promotion": "See official website for active campaigns"
                })
                
        print("BOT API fetched successfully.")
    except Exception as e:
        print(f"Failed to fetch from BOT API: {e}")
        
    return data_to_save

def run_scraper(output_path):
    print("Starting Bank Loans Scraper...")
    all_data = scrape_bot_api()
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)
        
    print(f"Bank loans data saved to {output_path}")

if __name__ == "__main__":
    # Test run
    run_scraper("../data/raw/bank_loans_raw.json")
