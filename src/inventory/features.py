#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import PurePosixPath

YEAR_RE = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")

def normalise_path(value: object) -> str:
    text = str(value or "").replace("\\", "/")
    if not text.startswith("/"):
        text = "/" + text
    return text

def path_features(path: object) -> dict:
    p = normalise_path(path)
    pp = PurePosixPath(p)
    name = pp.name
    stem = pp.stem
    suffix = pp.suffix.lower().lstrip(".")
    parts = [x for x in pp.parts if x != "/"]
    parent = str(pp.parent)
    tokens = re.findall(r"[A-Za-z0-9]+", stem.lower())
    years = YEAR_RE.findall(name)
    
    return {
        "path": p,
        "filename": name,
        "filename_stem": stem,
        "extension": suffix,
        "parent": parent,
        "depth": len(parts),
        "top_level": parts[0] if parts else "",
        "filename_tokens": tokens,
        "year_tokens": [int(y) for y in years],
    }

def classify_extension(ext: str) -> str:
    ext = (ext or "").lower()
    if ext in {"pdf", "doc", "docx", "odt", "rtf", "txt", "md"}:
        return "document"
    if ext in {"xls", "xlsx", "csv", "ods"}:
        return "spreadsheet"
    if ext in {"ppt", "pptx", "odp"}:
        return "presentation"
    if ext in {"jpg", "jpeg", "png", "gif", "webp", "heic", "tif", "tiff"}:
        return "image"
    if ext in {"mp4", "mkv", "mov", "avi", "webm"}:
        return "video"
    if ext in {"mp3", "wav", "flac", "m4a", "ogg", "aac"}:
        return "audio"
    if ext in {"zip", "7z", "rar", "tar", "gz"}:
        return "archive"
    return "other"