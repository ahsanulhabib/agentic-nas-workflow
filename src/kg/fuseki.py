import requests
from pathlib import Path

class FusekiClient:
    def __init__(self, base_url: str, dataset: str):
        self.data_url = f"{base_url.rstrip('/')}/{dataset.strip('/')}/data"

    def publish_graph(self, turtle_file: Path):
        """Pushes the .ttl file to Apache Jena."""
        print(f"📡 Publishing Graph to Apache Jena ({self.data_url})...")
        payload = turtle_file.read_bytes()
        r = requests.put(
            f"{self.data_url}?default",
            data=payload,
            headers={"Content-Type": "text/turtle"}
        )
        r.raise_for_status()
        print("✅ Graph successfully published to Fuseki.")