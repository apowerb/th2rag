import os

from dotenv import load_dotenv

dotenv_path = os.getenv("WORK_DIR", default=os.getcwd()) + "/.env"

load_dotenv(dotenv_path)

S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_ACCESS_KEY_SECRET = os.getenv("S3_ACCESS_KEY_SECRET")
S3_REGION = os.getenv("S3_REGION")
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
