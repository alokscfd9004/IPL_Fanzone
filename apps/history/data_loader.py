# Kaggle IPL Dataset processing pipeline
# Downloads the public dataset "slidescope/ipl-seasons-2008-to-2025-dataset"
# via kagglehub (no API key needed) and converts it to the JSON structure
# used by the history/analysis views. Results are cached in data/ipl_processed.json
# so the heavy CSV parsing (47MB ball-by-ball) runs only when the dataset changes.

import json
import os
from pathlib import Path

DATASET = "slidescope/ipl-seasons-2008-to-2025-dataset"

# Team ID -> (short_name, full_name)
# IDs are stable in the source dataset. Some franchises changed names:
# 2: Deccan Chargers (2008-2012) -> Sunrisers Hyderabad (2013+)
# 252: Delhi Daredevils -> Delhi Capitals | 494: Kings XI Punjab -> Punjab Kings
TEAM_MAP = {
    "1": ("RCB", "Royal Challengers Bengaluru"),
    "2": ("SRH", "Sunrisers Hyderabad"),
    "3": ("MI", "Mumbai Indians"),
    "4": ("RPS", "Rising Pune Supergiant"),
    "5": ("GL", "Gujarat Lions"),
    "6": ("KKR", "Kolkata Knight Riders"),
    "129": ("CSK", "Chennai Super Kings"),
    "134": ("RR", "Rajasthan Royals"),
    "252": ("DC", "Delhi Capitals"),
    "494": ("PBKS", "Punjab Kings"),
    "614": ("LSG", "Lucknow Super Giants"),
    "615": ("GT", "Gujarat Titans"),
    "1414": ("PWI", "Pune Warriors"),
    "1419": ("KTK", "Kochi Tuskers"),
}

TEAM_COLORS = {
    "MI": "#004BA0", "CSK": "#FDB913", "RCB": "#EC1C24", "KKR": "#3A225D",
    "SRH": "#FF822A", "RR": "#EA1A85", "PBKS": "#ED1B24", "DC": "#00008B",
    "GT": "#1C1C6B", "LSG": "#002147", "RPS": "#D81E5B", "GL": "#FF7F27",
    "PWI": "#2E8B8B", "KTK": "#4B0082",
}

TEAM_LOGOS = {
    "MI": "🔵", "CSK": "🦁", "RCB": "🦅", "KKR": "⚡", "SRH": "🌟",
    "RR": "💎", "PBKS": "👑", "DC": "🦅", "GT": "🦁", "LSG": "🌊",
    "RPS": "🐉", "GL": "🐯", "PWI": "🌴", "KTK": "🐘",
}

# bowler-credited dismissal kinds (wickets counting for the Purple Cap)
BOWLER_WICKETS = {"bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket"}


# Historical franchise names (ID -> [(until_year, name)])
LINEAGE = {
    "2": [(2012, "Deccan Chargers")],        # became Sunrisers Hyderabad in 2013
    "252": [(2018, "Delhi Daredevils")],     # became Delhi Capitals in 2019
    "494": [(2020, "Kings XI Punjab"), (2021, "Punjab Kings")],
}


def _team(tid, year=None):
    short, modern = TEAM_MAP.get(str(int(tid)), ("UNK", f"Team {tid}"))
    if year is not None:
        for until, old_name in LINEAGE.get(str(int(tid)), []):
            if year <= until:
                return short, old_name
    return short, modern


def _season_year(raw):
    """'2020/21' -> 2020, '2008' -> 2008"""
    return int(str(raw).split("/")[0])


def process_dataset(progress=print):
    """Download + parse the Kaggle dataset. Returns:
    {
      "seasons": {2008: {"champion": ..., "matches": ..., "sixes": ...}, ...},
      "details": {2008: {"teams": 10, "orange_cap": {...}, "points_table": [...]}, ...}
    }
    """
    import kagglehub
    import pandas as pd

    progress("Downloading Kaggle dataset (first run ~2.3MB zip, 47MB extracted)...")
    ds_path = Path(kagglehub.dataset_download(DATASET))
    progress(f"Dataset at {ds_path}")

    matches = pd.read_csv(ds_path / "all_ipl_matches_data.csv")
    matches["year"] = matches["season"].map(_season_year)

    balls = pd.read_csv(
        ds_path / "all_ball_by_ball_data.csv",
        usecols=["season_id", "match_id", "batter", "bowler", "team_batting",
                 "team_bowling", "batter_runs", "is_wicket", "wicket_kind"],
    )
    balls["year"] = balls["season_id"].map(_season_year)
    progress(f"Loaded {len(matches):,} matches and {len(balls):,} deliveries")

    seasons, details = {}, {}

    for year, mgrp in matches.groupby("year"):
        year = int(year)
        bgrp = balls[balls["year"] == year]

        # ── season totals ──
        sixes = int((bgrp["batter_runs"] == 6).sum())
        fours = int((bgrp["batter_runs"] == 4).sum())

        # champion / runner-up = last match of the season (the final)
        final = mgrp.sort_values("match_date").iloc[-1]
        champ_short, champ_name = _team(final["match_winner"], year)
        loser_id = final["team1"] if final["team2"] == final["match_winner"] else final["team2"]
        _, runner_name = _team(loser_id, year)

        seasons[year] = {
            "champion": champ_name,
            "runner_up": runner_name,
            "matches": int(len(mgrp)),
            "sixes": sixes,
            "fours": fours,
            "venues": int(mgrp["venue"].nunique()),
        }

        # ── player leaderboards ──
        runs = bgrp.groupby("batter")["batter_runs"].sum().sort_values(ascending=False)
        oc_player, oc_runs = runs.index[0], int(runs.iloc[0])
        wkts = (bgrp[bgrp["wicket_kind"].isin(BOWLER_WICKETS)]
                .groupby("bowler").size().sort_values(ascending=False))
        pc_player, pc_wkts = wkts.index[0], int(wkts.iloc[0])
        f4 = (bgrp[bgrp["batter_runs"] == 4].groupby("batter").size().sort_values(ascending=False))
        s6 = (bgrp[bgrp["batter_runs"] == 6].groupby("batter").size().sort_values(ascending=False))

        # 50s / 100s from per-innings batter scores
        inns = (bgrp.groupby(["match_id", "batter"])["batter_runs"].sum())
        half_centuries = int(((inns >= 50) & (inns < 100)).sum())
        centuries = int((inns >= 100).sum())

        # ── points table (win=2, tie/NR=1) ──
        pts = {}
        all_teams = pd.concat([mgrp["team1"], mgrp["team2"]]).dropna().unique()
        for t in all_teams:
            s, n = _team(t, year)
            pts[s] = {"team": n, "logo": s, "pld": 0, "won": 0, "lost": 0,
                      "nr": 0, "tie": 0, "pts": 0}
        for _, row in mgrp.iterrows():
            # skip playoff games (NaN match_number) — league table only
            if pd.isna(row.get("match_number")):
                continue
            t1, t2 = _team(row["team1"])[0], _team(row["team2"])[0]
            if pd.isna(row["team1"]) or pd.isna(row["team2"]):
                continue
            pts[t1]["pld"] += 1
            pts[t2]["pld"] += 1
            if pd.isna(row["match_winner"]):
                pts[t1]["nr"] += 1; pts[t2]["nr"] += 1
                pts[t1]["pts"] += 1; pts[t2]["pts"] += 1
            elif row["match_winner"] == row["team1"]:
                pts[t1]["won"] += 1; pts[t1]["pts"] += 2; pts[t2]["lost"] += 1
            elif row["match_winner"] == row["team2"]:
                pts[t2]["won"] += 1; pts[t2]["pts"] += 2; pts[t1]["lost"] += 1

        # batting/bowling team names for cap holders
        oc_team = _team(bgrp[bgrp["batter"] == oc_player]["team_batting"].mode()[0])[1] \
            if "team_batting" in bgrp.columns and len(bgrp) else "—"

        details[year] = {
            "teams": int(len(all_teams)),
            "half_centuries": half_centuries,
            "centuries": centuries,
            "orange_cap": {"player": oc_player, "team": oc_team, "runs": oc_runs},
            "purple_cap": {"player": pc_player, "team": _wicket_team(bgrp, pc_player), "wickets": pc_wkts},
            "most_fours": {"player": f4.index[0], "team": "—", "count": int(f4.iloc[0])},
            "most_sixes": {"player": s6.index[0], "team": "—", "count": int(s6.iloc[0])},
            "points_table": sorted(pts.values(), key=lambda x: (-x["pts"], x["team"])),
        }
        progress(f"  ✔ {year}: {champ_name} 🏆 ({len(mgrp)} matches, {sixes} sixes)")

    return {"seasons": seasons, "details": details}


def _wicket_team(bgrp, bowler):
    try:
        return _team(bgrp[bgrp["bowler"] == bowler]["team_bowling"].mode()[0])[1]
    except Exception:
        return "—"


def processed_file_path(base_dir):
    return Path(base_dir) / "data" / "ipl_processed.json"


def load_processed(base_dir):
    """Return cached processed dataset or None."""
    fp = processed_file_path(base_dir)
    if not fp.exists():
        return None
    try:
        with open(fp) as f:
            data = json.load(f)
        return {int(y): s for y, s in data["seasons"].items()}, \
               {int(y): d for y, d in data["details"].items()}
    except Exception:
        return None


def save_processed(base_dir, payload):
    fp = processed_file_path(base_dir)
    fp.parent.mkdir(parents=True, exist_ok=True)
    with open(fp, "w") as f:
        json.dump(payload, f)
    return fp
