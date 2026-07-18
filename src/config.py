import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL")
NC_USER = os.getenv("NEXTCLOUD_USER")
NC_PASS = os.getenv("NEXTCLOUD_APP_PASSWORD")
INGEST_DIR = os.getenv("INGEST_DIR", "/cloud_ingest/gdrive_ahabib9387")

if not NC_PASS:
    raise ValueError("CRITICAL: Nextcloud credentials not found in .env!")