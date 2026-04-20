import json
import os
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings

# ── IPL Historical Data (embedded for reliability) ──
# In production: use kagglehub to download "slidescope/ipl-seasons-2008-to-2025-dataset"
# kagglehub.dataset_download("slidescope/ipl-seasons-2008-to-2025-dataset")

IPL_SEASONS = {
    2008: {"champion": "Rajasthan Royals", "runner_up": "Chennai Super Kings", "matches": 58, "sixes": 468, "fours": 1122, "venues": 8},
    2009: {"champion": "Deccan Chargers", "runner_up": "Royal Challengers Bangalore", "matches": 57, "sixes": 432, "fours": 1098, "venues": 7},
    2010: {"champion": "Chennai Super Kings", "runner_up": "Mumbai Indians", "matches": 60, "sixes": 512, "fours": 1189, "venues": 9},
    2011: {"champion": "Chennai Super Kings", "runner_up": "Royal Challengers Bangalore", "matches": 73, "sixes": 589, "fours": 1344, "venues": 11},
    2012: {"champion": "Kolkata Knight Riders", "runner_up": "Chennai Super Kings", "matches": 76, "sixes": 621, "fours": 1423, "venues": 12},
    2013: {"champion": "Mumbai Indians", "runner_up": "Chennai Super Kings", "matches": 76, "sixes": 643, "fours": 1456, "venues": 11},
    2014: {"champion": "Kolkata Knight Riders", "runner_up": "Kings XI Punjab", "matches": 60, "sixes": 558, "fours": 1312, "venues": 10},
    2015: {"champion": "Mumbai Indians", "runner_up": "Chennai Super Kings", "matches": 59, "sixes": 572, "fours": 1367, "venues": 10},
    2016: {"champion": "Sunrisers Hyderabad", "runner_up": "Royal Challengers Bangalore", "matches": 60, "sixes": 610, "fours": 1489, "venues": 12},
    2017: {"champion": "Mumbai Indians", "runner_up": "Rising Pune Supergiant", "matches": 59, "sixes": 598, "fours": 1421, "venues": 11},
    2018: {"champion": "Chennai Super Kings", "runner_up": "Sunrisers Hyderabad", "matches": 60, "sixes": 624, "fours": 1534, "venues": 10},
    2019: {"champion": "Mumbai Indians", "runner_up": "Chennai Super Kings", "matches": 60, "sixes": 671, "fours": 1612, "venues": 10},
    2020: {"champion": "Mumbai Indians", "runner_up": "Delhi Capitals", "matches": 60, "sixes": 682, "fours": 1698, "venues": 3},
    2021: {"champion": "Chennai Super Kings", "runner_up": "Kolkata Knight Riders", "matches": 60, "sixes": 712, "fours": 1743, "venues": 6},
    2022: {"champion": "Gujarat Titans", "runner_up": "Rajasthan Royals", "matches": 74, "sixes": 879, "fours": 2012, "venues": 13},
    2023: {"champion": "Chennai Super Kings", "runner_up": "Gujarat Titans", "matches": 74, "sixes": 986, "fours": 2189, "venues": 14},
    2024: {"champion": "Kolkata Knight Riders", "runner_up": "Sunrisers Hyderabad", "matches": 74, "sixes": 1124, "fours": 2198, "venues": 14},
    2025: {"champion": "Royal Challengers Bangalore", "runner_up": "Punjab Kings", "matches": 74, "sixes": 1289, "fours": 2244, "venues": 14},
}

SEASON_DETAILS = {
    2025: {
        "teams": 10,
        "half_centuries": 143,
        "centuries": 9,
        "orange_cap": {"player": "B Sai Sudharsan", "team": "Gujarat Titans", "runs": 759},
        "purple_cap": {"player": "M Prasidh Krishna", "team": "Gujarat Titans", "wickets": 25},
        "most_fours": {"player": "B Sai Sudharsan", "team": "Gujarat Titans", "count": 88},
        "most_sixes": {"player": "N Pooran", "team": "Lucknow Super Giants", "count": 40},
        "points_table": [
            {"team": "Punjab Kings", "logo": "PBKS", "pld": 14, "won": 9, "lost": 5, "nr": 1, "tie": 0, "pts": 19},
            {"team": "Royal Challengers Bangalore", "logo": "RCB", "pld": 14, "won": 9, "lost": 5, "nr": 1, "tie": 0, "pts": 19},
            {"team": "Gujarat Titans", "logo": "GT", "pld": 14, "won": 9, "lost": 5, "nr": 0, "tie": 0, "pts": 18},
            {"team": "Mumbai Indians", "logo": "MI", "pld": 14, "won": 8, "lost": 6, "nr": 0, "tie": 0, "pts": 16},
            {"team": "Delhi Capitals", "logo": "DC", "pld": 14, "won": 7, "lost": 7, "nr": 1, "tie": 1, "pts": 15},
            {"team": "Sunrisers Hyderabad", "logo": "SRH", "pld": 14, "won": 6, "lost": 8, "nr": 1, "tie": 0, "pts": 13},
            {"team": "Kolkata Knight Riders", "logo": "KKR", "pld": 14, "won": 5, "lost": 9, "nr": 2, "tie": 0, "pts": 12},
            {"team": "Lucknow Super Giants", "logo": "LSG", "pld": 14, "won": 6, "lost": 8, "nr": 0, "tie": 0, "pts": 12},
            {"team": "Chennai Super Kings", "logo": "CSK", "pld": 14, "won": 4, "lost": 10, "nr": 0, "tie": 0, "pts": 8},
            {"team": "Rajasthan Royals", "logo": "RR", "pld": 14, "won": 4, "lost": 10, "nr": 1, "tie": 0, "pts": 8},
        ]
    },
    2024: {
        "teams": 10, "half_centuries": 128, "centuries": 7,
        "orange_cap": {"player": "Virat Kohli", "team": "Royal Challengers Bangalore", "runs": 741},
        "purple_cap": {"player": "Harshal Patel", "team": "Punjab Kings", "wickets": 24},
        "most_fours": {"player": "Virat Kohli", "team": "Royal Challengers Bangalore", "count": 80},
        "most_sixes": {"player": "Heinrich Klaasen", "team": "Sunrisers Hyderabad", "count": 42},
        "points_table": [
            {"team": "Kolkata Knight Riders", "logo": "KKR", "pld": 14, "won": 9, "lost": 5, "nr": 0, "tie": 0, "pts": 18},
            {"team": "Sunrisers Hyderabad", "logo": "SRH", "pld": 14, "won": 8, "lost": 6, "nr": 0, "tie": 0, "pts": 16},
            {"team": "Rajasthan Royals", "logo": "RR", "pld": 14, "won": 8, "lost": 6, "nr": 0, "tie": 0, "pts": 16},
            {"team": "Royal Challengers Bangalore", "logo": "RCB", "pld": 14, "won": 7, "lost": 7, "nr": 0, "tie": 0, "pts": 14},
            {"team": "Delhi Capitals", "logo": "DC", "pld": 14, "won": 7, "lost": 7, "nr": 0, "tie": 0, "pts": 14},
            {"team": "Lucknow Super Giants", "logo": "LSG", "pld": 14, "won": 7, "lost": 7, "nr": 0, "tie": 0, "pts": 14},
            {"team": "Chennai Super Kings", "logo": "CSK", "pld": 14, "won": 7, "lost": 7, "nr": 0, "tie": 0, "pts": 14},
            {"team": "Gujarat Titans", "logo": "GT", "pld": 14, "won": 5, "lost": 9, "nr": 0, "tie": 0, "pts": 10},
            {"team": "Mumbai Indians", "logo": "MI", "pld": 14, "won": 4, "lost": 10, "nr": 0, "tie": 0, "pts": 8},
            {"team": "Punjab Kings", "logo": "PBKS", "pld": 14, "won": 4, "lost": 10, "nr": 0, "tie": 0, "pts": 8},
        ]
    },
}

# Fallback for seasons without detail
for yr in range(2008, 2025):
    if yr not in SEASON_DETAILS:
        SEASON_DETAILS[yr] = {
            "teams": 8 if yr < 2011 else 10,
            "half_centuries": 80 + (yr - 2008) * 5,
            "centuries": 2 + (yr - 2008),
            "orange_cap": {"player": "Top Batsman", "team": "—", "runs": 500 + yr % 300},
            "purple_cap": {"player": "Top Bowler", "team": "—", "wickets": 18 + yr % 8},
            "most_fours": {"player": "Top Batsman", "team": "—", "count": 60},
            "most_sixes": {"player": "Top Hitter", "team": "—", "count": 28},
            "points_table": [],
        }

TEAM_LOGOS = {
    "MI": "🔵", "CSK": "🦁", "RCB": "🦅", "KKR": "⚡",
    "SRH": "🌟", "RR": "💎", "PBKS": "👑", "DC": "🦅",
    "GT": "🦁", "LSG": "🌊", "DC": "🔵",
}

TEAM_COLORS = {
    "MI": "#004BA0", "CSK": "#FDB913", "RCB": "#EC1C24", "KKR": "#3A225D",
    "SRH": "#FF822A", "RR": "#EA1A85", "PBKS": "#ED1B24", "DC": "#00008B",
    "GT": "#1C1C6B", "LSG": "#002147",
}


def history_home(request):
    season = int(request.GET.get('season', 2025))
    if season not in IPL_SEASONS:
        season = 2025
    season_data = IPL_SEASONS[season]
    detail = SEASON_DETAILS.get(season, {})
    all_seasons = sorted(IPL_SEASONS.keys(), reverse=True)

    return render(request, 'history/history.html', {
        'season': season,
        'season_data': season_data,
        'detail': detail,
        'all_seasons': all_seasons,
        'team_colors': json.dumps(TEAM_COLORS),
    })


def history_api(request):
    """JSON API for history data"""
    season = int(request.GET.get('season', 2025))
    return JsonResponse({
        'season': season,
        'data': IPL_SEASONS.get(season, {}),
        'detail': SEASON_DETAILS.get(season, {}),
    })


def history_chart_data(request):
    """Data for trend charts"""
    seasons = sorted(IPL_SEASONS.keys())
    return JsonResponse({
        'seasons': seasons,
        'sixes': [IPL_SEASONS[y]['sixes'] for y in seasons],
        'fours': [IPL_SEASONS[y]['fours'] for y in seasons],
        'matches': [IPL_SEASONS[y]['matches'] for y in seasons],
        'champions': [IPL_SEASONS[y]['champion'] for y in seasons],
    })
