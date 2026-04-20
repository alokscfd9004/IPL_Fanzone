import json
import re
import time
import os
from django.shortcuts import render
from django.http import JsonResponse
from django.core.cache import cache
from datetime import timedelta

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_SCRAPER = True
except ImportError:
    HAS_SCRAPER = False

# API Rate limiting - Max 1 call per session
API_CALL_LIMIT = 1  # Allow 1 call
API_CALL_TIMEOUT = 90  # 1.5 minutes in seconds
CACHE_TIMEOUT = 1800  # 30 minutes in seconds

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.cricbuzz.com/',
}

CRICAPI_KEY = os.getenv('CRICAPI_KEY', '')


def check_api_rate_limit():
    """Check if API call limit exceeded (1 call every 1.5 minutes)"""
    cache_key = 'cricapi_call_count'
    last_call_time = cache.get(cache_key)

    if last_call_time:
        time_since_last_call = time.time() - last_call_time
        if time_since_last_call < API_CALL_TIMEOUT:
            return False, f"⚠️ API limit reached. Try again in {int(API_CALL_TIMEOUT - time_since_last_call)} seconds."

    cache.set(cache_key, time.time(), API_CALL_TIMEOUT)
    return True, None


def get_from_cache_or_api(cache_key, api_func, *args):
    """Try cache first, then API with rate limiting"""
    # Try cache first
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data, "✅ Data from cache (no API call used)"
    
    # Check rate limit before API call
    can_call, message = check_api_rate_limit()
    if not can_call:
        return get_mock_data(), message
    
    # Make API call
    try:
        data = api_func(*args)
        cache.set(cache_key, data, CACHE_TIMEOUT)
        return data, "✅ Data from API"
    except Exception as e:
        return get_mock_data(), f"⚠️ API error: {str(e)}"


def get_cricbuzz_live():
    """Scrape live match list from Cricbuzz with caching and rate limiting"""
    cache_key = 'cricbuzz_live_matches'
    return get_from_cache_or_api(cache_key, _fetch_cricbuzz_live)

def _fetch_cricbuzz_live():
    if not HAS_SCRAPER:
        return get_mock_live_matches()
    try:
        url = "https://www.cricbuzz.com/cricket-match/live-scores"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')

        matches = []
        cards = soup.select('.cb-mtch-lst .cb-col-100.cb-col')[:8]

        for card in cards:
            try:
                title_el = card.select_one('.cb-lv-scrs-well a')
                status_el = card.select_one('.cb-text-live, .cb-text-complete, .cb-text-preview')
                score_els = card.select('.cb-lv-scrs-well-live')

                if not title_el:
                    continue

                href = title_el.get('href', '')
                match_id = ''
                if '/live-scores/' in href:
                    match_id = href.split('/live-scores/')[-1].split('/')[0]

                status_text = status_el.text.strip() if status_el else 'Upcoming'
                status_class = status_el.get('class', []) if status_el else []
                is_live = 'cb-text-live' in str(status_class)

                teams_scores = []
                for el in score_els:
                    teams_scores.append(el.text.strip())

                matches.append({
                    'id': match_id,
                    'title': title_el.text.strip(),
                    'href': 'https://www.cricbuzz.com' + href,
                    'status': status_text,
                    'is_live': is_live,
                    'scores': teams_scores,
                })
            except:
                continue

        return matches
    except Exception as e:
        print(f"Cricbuzz scrape error: {e}")
        return get_mock_live_matches()


def get_match_scorecard(match_id):
    """Scrape detailed scorecard from Cricbuzz with caching and rate limiting"""
    cache_key = f'cricbuzz_scorecard_{match_id}'
    return get_from_cache_or_api(cache_key, _fetch_match_scorecard, match_id)

def _fetch_match_scorecard(match_id):
    if not HAS_SCRAPER:
        return get_mock_scorecard()
    try:
        url = f"https://www.cricbuzz.com/live-cricket-scorecard/{match_id}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')

        scorecard = {
            'match_title': '',
            'status': '',
            'innings': [],
        }

        title_el = soup.select_one('h1.cb-nav-hdr')
        if title_el:
            scorecard['match_title'] = title_el.text.strip()

        status_el = soup.select_one('.cb-text-complete, .cb-text-live')
        if status_el:
            scorecard['status'] = status_el.text.strip()

        innings_sections = soup.select('.cb-ltst-wgt-hdr')
        batting_tables = soup.select('.table.cb-batting-ard')

        for i, table in enumerate(batting_tables[:4]):
            rows = table.select('tr')
            batsmen = []
            for row in rows:
                cols = row.select('td')
                if len(cols) >= 7:
                    name_el = cols[0].select_one('a')
                    if not name_el:
                        continue
                    name = name_el.text.strip()
                    if name in ('Batters', 'Did not bat', 'Fall of Wickets'):
                        continue
                    batsmen.append({
                        'name': name,
                        'dismissal': cols[1].text.strip() if len(cols) > 1 else '',
                        'runs': cols[2].text.strip() if len(cols) > 2 else '0',
                        'balls': cols[3].text.strip() if len(cols) > 3 else '0',
                        'fours': cols[4].text.strip() if len(cols) > 4 else '0',
                        'sixes': cols[5].text.strip() if len(cols) > 5 else '0',
                        'sr': cols[6].text.strip() if len(cols) > 6 else '0',
                    })

            innings_title = innings_sections[i].text.strip() if i < len(innings_sections) else f"Innings {i+1}"
            total_el = table.select_one('.cb-col-100.cb-col.cb-scrd-itms')

            scorecard['innings'].append({
                'title': innings_title,
                'batsmen': batsmen,
                'total': total_el.text.strip() if total_el else '',
            })

        return scorecard

    except Exception as e:
        print(f"Scorecard scrape error: {e}")
        return get_mock_scorecard()


def get_mock_live_matches():
    return [
        {
            'id': 'mock-1',
            'title': 'Mumbai Indians vs Chennai Super Kings, IPL 2025',
            'href': '#',
            'status': 'MI won by 7 wickets',
            'is_live': False,
            'scores': ['CSK 165/8 (20)', 'MI 166/3 (18.4)'],
        },
        {
            'id': 'mock-2',
            'title': 'RCB vs KKR, IPL 2025',
            'href': '#',
            'status': '2nd Innings: KKR 98/4 (12.3)',
            'is_live': True,
            'scores': ['RCB 176/6 (20)', 'KKR 98/4 (12.3)'],
        },
    ]


def get_mock_scorecard():
    return {
        'match_title': 'Demo Match - IPL 2025',
        'status': 'Live',
        'innings': [
            {
                'title': 'Mumbai Indians Innings 1',
                'batsmen': [
                    {'name': 'Rohit Sharma', 'dismissal': 'c Dhoni b Jadeja', 'runs': '56', 'balls': '38', 'fours': '6', 'sixes': '3', 'sr': '147.4'},
                    {'name': 'Ishan Kishan', 'dismissal': 'b Bumrah', 'runs': '48', 'balls': '32', 'fours': '5', 'sixes': '2', 'sr': '150.0'},
                    {'name': 'Suryakumar Yadav', 'dismissal': 'not out', 'runs': '89', 'balls': '51', 'fours': '8', 'sixes': '5', 'sr': '174.5'},
                ],
                'total': '196/4 (20 Ov)',
            }
        ],
    }


# ── VIEWS ──

def scorecard_home(request):
    matches = get_cricbuzz_live()
    return render(request, 'scorecard/scorecard.html', {'matches': matches})


def scorecard_detail(request, match_id):
    scorecard = get_match_scorecard(match_id)
    return render(request, 'scorecard/scorecard_detail.html', {'scorecard': scorecard, 'match_id': match_id})


def live_matches_api(request):
    matches = get_cricbuzz_live()
    return JsonResponse({'matches': matches})


def scorecard_api(request, match_id):
    scorecard = get_match_scorecard(match_id)
    return JsonResponse(scorecard)
