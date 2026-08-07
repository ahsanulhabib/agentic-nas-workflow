#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter

import pandas as pd


def top_level_profile(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby("top_level", dropna=False)
        .agg(
            files=("path", "count"),
            total_size=("size", "sum"),
            directories=("parent", "nunique"),
            max_depth=("depth", "max"),
        )
        .reset_index()
        .sort_values("files", ascending=False)
    )
    return grouped

def extension_profile(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["extension", "media_class"], dropna=False)
        .size()
        .reset_index(name="files")
        .sort_values("files", ascending=False)
    )

def directory_profile(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("parent", dropna=False)
        .agg(files=("path", "count"), max_depth=("depth", "max"))
        .reset_index()
        .sort_values("files", ascending=False)
    )

def token_profile(df: pd.DataFrame, top_n: int = 100) -> pd.DataFrame:
    counter = Counter()
    for values in df["filename_tokens"].dropna():
        counter.update(values)
    return pd.DataFrame(counter.most_common(top_n), columns=["token", "files"])

def summary(df: pd.DataFrame) -> dict:
    return {
        "files": int(len(df)),
        "top_levels": int(df["top_level"].nunique()),
        "directories": int(df["parent"].nunique()),
        "extensions": int(df["extension"].nunique()),
        "media_classes": int(df["media_class"].nunique()),
    }