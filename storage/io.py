"""Filesystem IO helpers.

We deliberately avoid a database — JSON for Sleeper API snapshots (matches
the response format), parquet for tabular NFL data (columnar + compressed).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# JSON (Sleeper snapshots)
# ---------------------------------------------------------------------------


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f)
    return path


def read_json(path: Path) -> Any:
    with path.open("r") as f:
        return json.load(f)


def json_exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def age_seconds(path: Path) -> float | None:
    if not path.exists():
        return None
    return time.time() - path.stat().st_mtime


# ---------------------------------------------------------------------------
# Parquet (NFL stats + derived frames)
# ---------------------------------------------------------------------------


def write_parquet(path: Path, df: pd.DataFrame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def read_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def read_parquet_or_empty(path: Path) -> pd.DataFrame:
    if path.exists():
        return read_parquet(path)
    return pd.DataFrame()
