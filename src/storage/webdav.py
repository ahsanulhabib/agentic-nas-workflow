from src.config import NEXTCLOUD_URL
import os
from webdav4.client import Client
from prefect.blocks.system import Secret

def create_webdav_client() -> Client:
    """Factory function to create a fresh, authenticated WebDAV client."""
    print("Authenticating with Prefect Vault...")
    nc_user = Secret.load("nextcloud-username").get()
    nc_pass = Secret.load("nextcloud-password").get()
    return Client(NEXTCLOUD_URL, auth=(nc_user, nc_pass))

def upload_file(client: Client, local_path: str, remote_path: str):
    """Idempotently uploads a file to Nextcloud, recursively creating parent folders."""
    folder_path = os.path.dirname(remote_path)
    
    # Split the path into parts and build it up one level at a time
    parts = [p for p in folder_path.split('/') if p]
    current_path = ""
    
    for part in parts:
        current_path += f"/{part}"
        if not client.exists(current_path):
            print(f"   [System] Creating missing remote folder: {current_path}")
            client.mkdir(current_path)
            
    client.upload_file(from_path=local_path, to_path=remote_path, overwrite=True)
    print(f"   [Success] Uploaded to -> {remote_path}")