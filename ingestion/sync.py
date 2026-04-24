"""Master sync script.

Run as a module:
    python -m ingestion.sync

Or import and call `sync_all()` from elsewhere. Idempotent — re-running
updates snapshots without duplicating anything.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

# macOS/framework Python often lacks root CAs wired into urllib. nfl_data_py
# uses urllib under the hood, so point it at certifi's bundle when available.
if "SSL_CERT_FILE" not in os.environ:
    try:
        import certifi  # type: ignore
        os.environ["SSL_CERT_FILE"] = certifi.where()
        os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except Exception:  # noqa: BLE001 - optional
        pass

import config
from ingestion import external, id_mapping, nfl_stats, sleeper_api
from storage import io as sio


@dataclass
class SyncResult:
    league_week: int | None
    num_rosters: int
    num_users: int
    matchup_weeks: list[int]
    nfl_frames: list[str]


def sync_sleeper(week_hint: int | None = None) -> SyncResult:
    league = sleeper_api.get_league(config.LEAGUE_ID)
    sio.write_json(config.SLEEPER_DIR / "league.json", league)

    rosters = sleeper_api.get_rosters(config.LEAGUE_ID)
    sio.write_json(config.SLEEPER_DIR / "rosters.json", rosters)

    users = sleeper_api.get_users(config.LEAGUE_ID)
    sio.write_json(config.SLEEPER_DIR / "users.json", users)

    traded = sleeper_api.get_traded_picks(config.LEAGUE_ID)
    sio.write_json(config.SLEEPER_DIR / "traded_picks.json", traded)

    drafts = sleeper_api.get_drafts(config.LEAGUE_ID)
    sio.write_json(config.SLEEPER_DIR / "drafts.json", drafts)
    for d in drafts or []:
        did = d.get("draft_id")
        if not did:
            continue
        picks = sleeper_api.get_draft_picks(did)
        sio.write_json(config.SLEEPER_DIR / f"draft_{did}_picks.json", picks)
        dtp = sleeper_api.get_draft_traded_picks(did)
        sio.write_json(config.SLEEPER_DIR / f"draft_{did}_traded_picks.json", dtp)

    state = sleeper_api.get_nfl_state()
    sio.write_json(config.SLEEPER_DIR / "nfl_state.json", state)
    current_week = state.get("week") if isinstance(state, dict) else None
    target_week = week_hint or current_week or 18

    matchup_weeks: list[int] = []
    for wk in range(1, int(target_week) + 1):
        m = sleeper_api.get_matchups(config.LEAGUE_ID, wk)
        if not m:
            continue
        sio.write_json(config.SLEEPER_DIR / f"matchups_week_{wk}.json", m)
        matchup_weeks.append(wk)
        t = sleeper_api.get_transactions(config.LEAGUE_ID, wk)
        sio.write_json(config.SLEEPER_DIR / f"transactions_week_{wk}.json", t)

    # Trending (optional, cheap, nice to have)
    try:
        sio.write_json(
            config.SLEEPER_DIR / "trending_adds.json",
            sleeper_api.get_trending("add"),
        )
        sio.write_json(
            config.SLEEPER_DIR / "trending_drops.json",
            sleeper_api.get_trending("drop"),
        )
    except Exception:  # noqa: BLE001 - trending is optional
        pass

    return SyncResult(
        league_week=current_week,
        num_rosters=len(rosters),
        num_users=len(users),
        matchup_weeks=matchup_weeks,
        nfl_frames=[],
    )


def sync_players_if_stale() -> bool:
    """Refresh Sleeper /players/nfl only if the cached copy is older than
    PLAYERS_DB_MAX_AGE_SECONDS. Returns True when refreshed."""
    path = config.SLEEPER_DIR / "players_nfl.json"
    age = sio.age_seconds(path)
    if age is not None and age < config.PLAYERS_DB_MAX_AGE_SECONDS:
        return False
    data = sleeper_api.get_players_nfl()
    sio.write_json(path, data)
    return True


def sync_nfl(skip_ngs: bool = False) -> list[str]:
    """Materialize parquet snapshots for the frames we use most."""
    written = nfl_stats.snapshot_frames_to_parquet()
    if not skip_ngs:
        ngs_written = nfl_stats.snapshot_ngs_to_parquet()
        written.update(ngs_written)
    return list(written.keys())


def sync_externals() -> dict[str, int]:
    """Pull FantasyPros externals. Returns row counts."""
    return external.snapshot_externals()


def sync_all(skip_pbp: bool = True, skip_players: bool = False, skip_externals: bool = False) -> SyncResult:
    res = sync_sleeper()
    if not skip_players:
        sync_players_if_stale()
    # ID map depends on both sides, so build after both.
    id_mapping.build_id_map()
    frames = sync_nfl()
    if not skip_pbp:
        nfl_stats.cache_pbp()
    if not skip_externals:
        ext_counts = sync_externals()
        if ext_counts:
            print("external frames:", ", ".join(f"{k}={v}" for k, v in ext_counts.items()))
    res.nfl_frames = frames
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Dynasty analytics data sync.")
    ap.add_argument("--skip-nfl", action="store_true", help="Only refresh Sleeper side.")
    ap.add_argument("--skip-ngs", action="store_true", help="Skip Next Gen Stats snapshot.")
    ap.add_argument("--skip-players", action="store_true", help="Do not refresh Sleeper /players/nfl.")
    ap.add_argument("--skip-externals", action="store_true", help="Skip FantasyPros/NGS pull.")
    ap.add_argument("--with-pbp", action="store_true", help="Also cache play-by-play.")
    args = ap.parse_args(argv)

    if args.skip_nfl:
        res = sync_sleeper()
        if not args.skip_players:
            sync_players_if_stale()
    else:
        res = sync_all(
            skip_pbp=not args.with_pbp,
            skip_players=args.skip_players,
            skip_externals=args.skip_externals,
        )

    print(
        f"sleeper: week={res.league_week} rosters={res.num_rosters} "
        f"users={res.num_users} matchup_weeks={len(res.matchup_weeks)}"
    )
    if res.nfl_frames:
        print("nfl frames written:", ", ".join(res.nfl_frames))
    return 0


if __name__ == "__main__":
    sys.exit(main())
