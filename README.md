# Waiver Raiders Football Analytics

A local + cloud-hosted analytics platform for a 12-team Sleeper dynasty league (half PPR, TE premium, superflex).

**Live app:** [waiver-raider.streamlit.app](https://waiver-raider.streamlit.app)

**League ID:** `1315773051115167744`

---

## Features

| Page | What it does |
|---|---|
| **Dashboard** | Your roster front-and-center — standings, age profile, competitive window |
| **Rookie Draft** | Prospect board (skill positions only), position scouts, NGS debut data, FantasyPros |
| **Weekly Lineup** | Start/sit optimizer, player deep-dive, rolling projections, scoring explainers |
| **Trends** | Breakout alerts, rolling production, xFP vs actual, Next Gen Stats |
| **Waivers** | Ranked pickups, platform-trending adds, FAAB bid calculator |
| **Player Compare** | Multi-player weekly trends, season totals, radar profile, raw stats |

---

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m ingestion.sync      # pull Sleeper + NFL data (~2-4 min first time)
streamlit run app.py
```

**Find your roster ID:**
```bash
python3 -c "
from analysis import common
for r in common.rosters():
    u = common.user_by_id(r.get('owner_id') or '') or {}
    print(f\"roster_id={r['roster_id']}  {u.get('display_name')}\")
"
```

Then set `MY_ROSTER_ID` in `config.py`.

---

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub (already done)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Pick repo `mmcint/waiver-raider`, branch `main`, file `app.py`
4. Under **Advanced → Secrets**, add:
   ```toml
   FANTASYPROS_API_KEY = "your_key_here"
   ```
5. Click **Deploy** — the app auto-syncs data on first startup

**After deploying:** update the redirect URL in `.github/redirect/index.html` with your actual Streamlit Cloud URL.

---

## Data sources

| Source | Cost | What it provides |
|---|---|---|
| Sleeper API | Free | League data — rosters, matchups, transactions, draft picks |
| nfl_data_py / nflverse | Free | Weekly stats, snap counts, rosters, combine data |
| Next Gen Stats | Free | Separation, CPOE, RYOE, time to throw, YAC over expected |
| FantasyPros API | Free key | Consensus rankings, ADP, rookie dynasty rankings |

---

## Sync schedule

```bash
# Weekly (Tuesday after games finalize)
python -m ingestion.sync

# Sleeper only (fast, during season)
python -m ingestion.sync --skip-nfl

# With play-by-play (large, occasional)
python -m ingestion.sync --with-pbp
```
