import os
from webdav4.client import Client
from src.config import NEXTCLOUD_URL, NC_USER, NC_PASS

# Initialize Zero-Trust WebDAV Client
client = Client(NEXTCLOUD_URL, auth=(NC_USER, NC_PASS))

def upload_file(local_path: str, remote_path: str):
    """Idempotently uploads a file to Nextcloud, creating folders if needed."""
    folder_path = os.path.dirname(remote_path)
    
    if not client.exists(folder_path):
        print(f"Creating remote folder: {folder_path}")
        client.mkdir(folder_path)
            
    client.upload_sync(remote_path=remote_path, local_path=local_path, overwrite=True)
    print(f"SUCCESS: Uploaded to -> {remote_path}")