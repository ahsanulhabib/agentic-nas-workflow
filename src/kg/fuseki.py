from __future__ import annotations  #noqa: EXE002

from pathlib import Path
from typing import Any

import requests


class FusekiClient:
    """Transactional Client for Apache Jena Fuseki TDB2."""
    
    def __init__(self, base_url: str, dataset: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.dataset = dataset.strip("/")
        self.timeout = timeout

    @property
    def query_url(self) -> str:
        return f"{self.base_url}/{self.dataset}/query"

    @property
    def data_url(self) -> str:
        return f"{self.base_url}/{self.dataset}/data"

    def health(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/$/ping", timeout=self.timeout)
            return r.ok
        except requests.RequestException:
            return False

    def replace_default_graph(self, turtle_file: Path | str) -> bool:
        """Atomically replaces the default graph in TDB2."""
        turtle_path = Path(turtle_file)
        if not turtle_path.exists():
            raise FileNotFoundError(f"TTL file not found at {turtle_path}")

        payload = turtle_path.read_bytes()
        response = requests.put(
            f"{self.data_url}?default",
            data=payload,
            headers={"Content-Type": "text/turtle"},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.status_code in [200, 201, 204]

    def query(self, sparql_query: str) -> dict[str, Any]:
        """Executes a SPARQL SELECT query and returns JSON results."""
        response = requests.post(
            self.query_url,
            data={"query": sparql_query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()