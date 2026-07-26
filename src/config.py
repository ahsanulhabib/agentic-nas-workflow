import os
from dotenv import load_dotenv

# 1. Load routing configuration from .env
load_dotenv()

NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "http://192.168.1.55:30027/remote.php/webdav")
INGEST_DIR = os.getenv("INGEST_DIR", "/cloud_ingest/gdrive_ahabib9387")

# Ensure Prefect knows where its own API is
os.environ["PREFECT_API_URL"] = os.getenv("PREFECT_API_URL", "http://192.168.1.55:4200/api")

from __future__ import annotations
import os
from pathlib import Path
from typing import Any
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"

def load_yaml(name: str) -> dict[str, Any]:
    with (CONFIG_DIR / name).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _env_override(config: dict[str, Any], env_name: str, path: tuple[str, ...]) -> None:
    value = os.getenv(env_name)
    if value is None:
        return
    node = config
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value

def load_settings() -> dict[str, Any]:
    settings = load_yaml("settings.yaml")
    _env_override(settings, "NAS_LEDGER_DB", ("paths", "ledger_db"))
    _env_override(settings, "NAS_FUSEKI_URL", ("kg", "fuseki_url"))
    _env_override(settings, "NAS_LLM_PROVIDER", ("llm", "provider"))
    _env_override(settings, "NAS_LLM_MODEL", ("llm", "model"))
    _env_override(settings, "NAS_LLM_BASE_URL", ("llm", "base_url"))
    return settings

def root_path(relative: str | Path) -> Path:
    path = Path(relative)
    return path if path.is_absolute() else ROOT / path