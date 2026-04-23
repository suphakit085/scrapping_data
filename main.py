import os
import sys

# Add the root directory to the Python path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.bank_loans import run_scraper as run_bank_scraper
from scrapers.reic_trends import scrape_dotproperty_trends
from utils.data_cleaner import clean_bank_loans, clean_reic_trends
from utils.aws_uploader import upload_to_s3

def main():
    print("========================================")
    print("Starting Automated Web Scraping Pipeline")
    print("========================================")
    
    raw_bank_path = "data/raw/bank_loans_raw.json"
    raw_reic_path = "data/raw/reic_trends_raw.json"
    processed_bank_path = "data/processed/bank_loans_clean.csv"
    processed_reic_path = "data/processed/reic_trends_clean.csv"
    
    # 1. Scrape Data
    print("\n[Phase 1] Scraping Data...")
    run_bank_scraper(raw_bank_path)
    scrape_dotproperty_trends(raw_reic_path)
    
    # 2. Clean Data
    print("\n[Phase 2] Cleaning and Processing Data...")
    clean_bank_loans(raw_bank_path, processed_bank_path)
    clean_reic_trends(raw_reic_path, processed_reic_path)
    
    # 3. Upload to AWS S3 (AWS Glue ETL entry point)
    print("\n[Phase 3] Uploading to AWS S3...")
    
    # IMPORTANT: Replace 'your-target-bucket-name' with your actual S3 bucket
    S3_BUCKET_NAME = "your-target-bucket-name"
    S3_PREFIX = "web-scraping-data/processed/" 
    
    # Note: These will print 'Credentials not available' if you haven't run `aws configure`
    # or set up AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your environment.
    upload_to_s3(processed_bank_path, S3_BUCKET_NAME, S3_PREFIX)
    upload_to_s3(processed_reic_path, S3_BUCKET_NAME, S3_PREFIX)
    
    print("\n========================================")
    print("Pipeline Execution Completed Successfully.")
    print("========================================")

if __name__ == "__main__":
    main()
