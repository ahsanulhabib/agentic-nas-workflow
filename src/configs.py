#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Dynamically find the root of the repository
ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"

def load_yaml(name: str) -> dict[str, Any]:
    """Reads a YAML file from the config directory."""
    with (CONFIG_DIR / name).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _env_override(config: dict[str, Any], env_name: str, path: tuple[str, ...]) -> None:
    """Allows local .env variables to override YAML settings safely."""
    value = os.getenv(env_name)
    if value is None:
        return
    node = config
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value

def load_settings() -> dict[str, Any]:
    """Loads settings.yaml and applies any local environment overrides."""
    settings = load_yaml("settings.yaml")
    
    # Optional local overrides (useful for testing on different machines or CI/CD)
    _env_override(settings, "NAS_LEDGER_DB", ("paths", "ledger_db"))
    _env_override(settings, "NAS_FUSEKI_URL", ("kg", "fuseki_url"))
    _env_override(settings, "NAS_LLM_PROVIDER", ("llm", "provider"))
    _env_override(settings, "NAS_LLM_MODEL", ("llm", "model"))
    _env_override(settings, "NAS_LLM_BASE_URL", ("llm", "base_url"))
    _env_override(settings, "NEXTCLOUD_URL", ("nextcloud", "url"))
    _env_override(settings, "NAS_VECTOR_MODEL", ("vector", "model_name"))
    _env_override(settings, "NAS_VECTOR_SIZE", ("vector", "vector_size"))
    
    return settings

def root_path(relative: str | Path) -> Path:
    """Safely resolves relative paths to the absolute project root."""
    path = Path(relative)
    return path if path.is_absolute() else ROOT / path