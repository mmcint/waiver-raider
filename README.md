# Dynasty Analytics Platform

Local analytics for a 12-team Sleeper dynasty league (half PPR, TE premium, superflex). See [`../dynasty-analytics-architecture.md`](../dynasty-analytics-architecture.md) for the full design.

**League ID:** `1315773051115167744`

## Setup

```bash
cd dynasty-analytics
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Every command below assumes the venv is active (`source .venv/bin/activate`). If you'd rather not activate, prefix with `.venv/bin/` — e.g. `.venv/bin/python -m ingestion.sync`.

## First-time sync

Pull Sleeper league data + NFL stats + build the ID crosswalk:

```bash
python -m ingestion.sync
```

Flags:
- `--skip-nfl` — only refresh Sleeper snapshots (fast)
- `--skip-players` — don't re-download the 5MB `/players/nfl` blob
- `--with-pbp` — also cache play-by-play (slow, large)

The `data/` directory is filesystem-only (JSON + parquet). Nothing goes to a database.

## Run the app

```bash
streamlit run app.py
```

Open the URL Streamlit prints. The landing page has sync buttons so you can refresh data without leaving the app.

## Pages

1. **Dashboard** — standings, scoring settings, your roster
2. **Rookie Draft** — prospect board (NFL draft + combine), historical hit rates by position × round, your pick inventory
3. **Weekly Lineup** — roster projections + greedy optimizer respecting QB / RB / WR / TE / FLEX / SUPER_FLEX slots
4. **Trends** — breakout alerts, snap-share ascending, xFP vs actual, rolling production
5. **Waivers** — ranked unrostered players, platform-trending adds, FAAB bid helper

Set `MY_ROSTER_ID` in `config.py` to pin your roster across pages.

## Project layout

```
dynasty-analytics/
├── app.py                      # Streamlit entry point
├── config.py                   # League ID, data paths, thresholds
├── requirements.txt
├── ingestion/
│   ├── sleeper_api.py          # Sleeper API client
│   ├── nfl_stats.py            # nfl_data_py wrapper
│   ├── id_mapping.py           # Sleeper <-> GSIS crosswalk
│   └── sync.py                 # Master sync (CLI + library)
├── storage/io.py               # JSON / parquet helpers
├── scoring/engine.py           # Applies Sleeper scoring_settings to weekly stats
├── analysis/
│   ├── common.py               # Cached loaders for pages
│   ├── trends.py               # Rolling, breakout, xFP
│   ├── waivers.py              # Available-player ranking
│   ├── weekly_optimizer.py     # Lineup optimizer
│   ├── rookie_draft.py         # Prospect board, hit rates
│   └── dynasty_value.py        # Age curves, contender/rebuild signal
├── pages/                      # Streamlit multi-page app
└── data/                       # gitignored; populated by ingestion.sync
```

## Validating the scoring engine

After your first sync, pick a completed week and compare:

```python
from analysis import common, trends
from scoring import engine
from storage import io as sio
import config

scored = trends.build_scored_weekly()
matchups = sio.read_json(config.SLEEPER_DIR / "matchups_week_5.json")
id_map = common.id_map()

print(engine.validate_against_sleeper(scored, week=5, season=2025, matchups=matchups, id_map=id_map))
```

The `engine_points` column should be within rounding of `sleeper_points`. If they diverge, a scoring-key mapping needs adjustment in `scoring/engine.py::SLEEPER_TO_WEEKLY`.

## What's implemented vs. scaffolded

- **Implemented:** All Phase 1 items (ingestion, ID map, scoring engine, dashboard) plus working versions of the trends, waiver, optimizer, and rookie draft modules with UI pages.
- **Scaffolded / lightweight:** The projection used by the lineup optimizer is a rolling mean — swap in your own source. xFP uses simple opportunity weights; a richer model goes in `analysis/trends.py::expected_fantasy_points`. Dynasty trade values (KTC/FantasyCalc) are stubbed in `analysis/dynasty_value.py`.

## Resource footprint

Tuned for a base M4 Mac mini per the architecture doc:
- Weekly / snaps / rosters cached as parquet for 3 seasons
- Play-by-play only on demand (`--with-pbp`)
- `downcast=True` on NFL frames
- Streamlit `@st.cache_data` is not applied by default — add it to `analysis/common.py` loaders if you want stricter memoization across pages
