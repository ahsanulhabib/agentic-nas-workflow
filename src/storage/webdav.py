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
    """
    Idempotently uploads a file to Nextcloud.
    """
    folder_path = os.path.dirname(remote_path)
    
    if not client.exists(folder_path):
        print(f"Creating remote folder: {folder_path}")
        client.mkdir(folder_path)
            
    client.upload_sync(remote_path=remote_path, local_path=local_path, overwrite=True)
    print(f"SUCCESS: Uploaded to -> {remote_path}")