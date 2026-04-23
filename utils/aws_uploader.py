import boto3
import os
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

def upload_to_s3(file_path, bucket_name, s3_prefix=""):
    """
    Uploads a file to an AWS S3 bucket.
    
    Parameters:
    - file_path: Local path to the file.
    - bucket_name: The name of the S3 bucket.
    - s3_prefix: Optional folder path inside the S3 bucket.
    """
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist.")
        return False
        
    file_name = os.path.basename(file_path)
    s3_key = f"{s3_prefix}{file_name}" if s3_prefix else file_name
    
    print(f"Uploading {file_name} to s3://{bucket_name}/{s3_key} ...")
    
    try:
        # Initialize the S3 client. It will automatically look for credentials in:
        # 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        # 2. ~/.aws/credentials file (set up via `aws configure`)
        s3_client = boto3.client('s3')
        
        s3_client.upload_file(file_path, bucket_name, s3_key)
        print(f"Successfully uploaded {file_name} to S3.")
        return True
        
    except FileNotFoundError:
        print(f"The file was not found")
        return False
    except NoCredentialsError:
        print("Credentials not available. Please configure AWS credentials.")
        return False
    except PartialCredentialsError:
        print("Incomplete AWS credentials found. Please check your configuration.")
        return False
    except Exception as e:
        print(f"An error occurred during upload: {e}")
        return False

if __name__ == "__main__":
    pass
