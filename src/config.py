import os
from dotenv import load_dotenv

# 1. Load routing configuration from .env
load_dotenv()

NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "http://192.168.1.55:30027/remote.php/webdav")
INGEST_DIR = os.getenv("INGEST_DIR", "/cloud_ingest/gdrive_ahabib9387")

# Ensure Prefect knows where its own API is
os.environ["PREFECT_API_URL"] = os.getenv("PREFECT_API_URL", "http://192.168.1.55:4200/api")