"""Thin wrapper around the Sleeper public API.

All endpoints referenced in the architecture doc are covered. No auth; we
just use `requests` with a reasonable timeout and a small retry.
"""

from __future__ import annotations

import time
from typing import Any

import requests

import config


class SleeperAPIError(RuntimeError):
    pass


def _get(path: str, params: dict[str, Any] | None = None, retries: int = 2) -> Any:
    url = f"{config.SLEEPER_BASE_URL}{path}"
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(
                url,
                params=params,
                timeout=config.SLEEPER_REQUEST_TIMEOUT_SECONDS,
            )
            if r.status_code == 429:
                # Backoff and retry
                time.sleep(1 + attempt)
                continue
            r.raise_for_status()
            if not r.text:
                return None
            return r.json()
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise SleeperAPIError(f"GET {url} failed: {exc}") from exc
    raise SleeperAPIError(f"GET {url} exhausted retries: {last_exc}")


# ---------------------------------------------------------------------------
# League-scoped endpoints
# ---------------------------------------------------------------------------


def get_league(league_id: str) -> dict:
    return _get(f"/league/{league_id}")


def get_rosters(league_id: str) -> list[dict]:
    return _get(f"/league/{league_id}/rosters") or []


def get_users(league_id: str) -> list[dict]:
    return _get(f"/league/{league_id}/users") or []


def get_matchups(league_id: str, week: int) -> list[dict]:
    return _get(f"/league/{league_id}/matchups/{week}") or []


def get_transactions(league_id: str, week: int) -> list[dict]:
    return _get(f"/league/{league_id}/transactions/{week}") or []


def get_traded_picks(league_id: str) -> list[dict]:
    return _get(f"/league/{league_id}/traded_picks") or []


def get_drafts(league_id: str) -> list[dict]:
    return _get(f"/league/{league_id}/drafts") or []


# ---------------------------------------------------------------------------
# Draft-scoped endpoints
# ---------------------------------------------------------------------------


def get_draft_picks(draft_id: str) -> list[dict]:
    return _get(f"/draft/{draft_id}/picks") or []


def get_draft_traded_picks(draft_id: str) -> list[dict]:
    return _get(f"/draft/{draft_id}/traded_picks") or []


# ---------------------------------------------------------------------------
# Global endpoints
# ---------------------------------------------------------------------------


def get_nfl_state() -> dict:
    return _get("/state/nfl") or {}


def get_players_nfl() -> dict:
    """Large (~5MB) player database. Cache locally and call at most daily."""
    return _get("/players/nfl") or {}


def get_trending(kind: str = "add", lookback_hours: int = 24, limit: int = 100) -> list[dict]:
    assert kind in {"add", "drop"}
    return _get(
        f"/players/nfl/trending/{kind}",
        params={"lookback_hours": lookback_hours, "limit": limit},
    ) or []
