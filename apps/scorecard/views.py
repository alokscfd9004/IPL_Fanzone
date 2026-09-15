import re
import time
import xml.etree.ElementTree as ET
from datetime import date
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.core.cache import cache

from ipl_platform.ratelimit import rate_limit

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_SCRAPER = True
except ImportError:
    HAS_SCRAPER = False

# Live data = free CricketData.org widgets (no key) + Cricbuzz scraping.
# Scraper rate limiting — keep a gap between external fetches.
API_CALL_TIMEOUT = 90  # 1.5 minutes in seconds
CACHE_TIMEOUT = 1800  # 30 minutes in seconds

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.cricbuzz.com/',
}

# ESPN Cricinfo official RSS — free, public, no API key, no rate limits.
# TTL is 2 min; our 90s rate-limit gate keeps us well within "polite" range.
ESPN_LIVE_RSS_URL = "https://www.espncricinfo.com/rss/livescores.xml"

# CricZop — free public site, server-rendered scorecards (batting/bowling/FOW).
# Used ONLY for the detail page: its homepage cards carry no live scores, so
# it can't serve the list — but one click deep it has the full innings tables.
CRICZOP_BASE = "https://www.criczop.com"
CRICZOP_CARDS_CACHE_KEY = 'criczop_match_cards'

# IPL has a season window — most days there's no IPL match. So the feed shows
# whatever cricket is live, and floats IPL games to the top with a gold flag
# the moment one appears.
IPL_MARKERS = (
    'IPL', 'Indian Premier League',
    'Mumbai Indians', 'Chennai Super Kings', 'Royal Challengers',
    'Kolkata Knight Riders', 'Sunrisers Hyderabad', 'Rajasthan Royals',
    'Punjab Kings', 'Delhi Capitals', 'Gujarat Titans', 'Lucknow Super Giants',
    'Kings XI Punjab', 'Delhi Daredevils', 'Deccan Chargers',
)


def classify_match(title):
    t = (title or '').lower()
    return 'IPL' if any(m.lower() in t for m in IPL_MARKERS) else 'Other'


# IPL runs ~late March → end of May. Outside that window there is no "live IPL"
# to show — instead tell fans when the next season starts.
def next_ipl_window(today=None):
    today = today or date.today()
    year = today.year
    # Before the usual window: season starts THIS year; otherwise next year.
    if today < date(year, 3, 20):
        season, start = year, date(year, 3, 20)
    else:
        season, start = year + 1, date(year + 1, 3, 20)
    return {
        'season': season,
        'start_date': start.isoformat(),
        'days_to_go': max((start - today).days, 0),
        'label': f"IPL {season} is expected to begin around 20 March {season}",
    }


def check_api_rate_limit():
    """Check if scraper fetch limit exceeded (1 fetch every 1.5 minutes)"""
    cache_key = 'scraper_last_call'
    last_call_time = cache.get(cache_key)

    if last_call_time:
        time_since_last_call = time.time() - last_call_time
        if time_since_last_call < API_CALL_TIMEOUT:
            return False, f"⚠️ API limit reached. Try again in {int(API_CALL_TIMEOUT - time_since_last_call)} seconds."

    cache.set(cache_key, time.time(), API_CALL_TIMEOUT)
    return True, None


def broadcast_live(matches, note):
    """Push fresh scores to every client connected on /ws/live/ (silently
    no-ops on serverless where the InMemory layer can't cross invocations)."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)('live_scores', {
                'type': 'live_score_update',
                'matches': matches,
                'note': note,
            })
    except Exception:
        pass


def get_cricbuzz_live():
    """Live match list with caching + rate limiting.

    Source chain: cache → ESPN Cricinfo RSS (free, no key) → Cricbuzz HTML
    scrape. Shows whatever cricket is on; when an IPL match appears it
    jumps to the top of the list flagged league='IPL'. If every source is
    down, returns an EMPTY list with a friendly note — never fake scores."""
    cache_key = 'cricbuzz_live_matches'

    cached = cache.get(cache_key)
    if cached:
        return _enrich_live(cached), "✅ Data from cache (no API call used)"

    can_call, message = check_api_rate_limit()
    if not can_call:
        return [], message or "⏳ Refreshing live scores — try again in a moment"

    for source_label, fetcher in (("ESPN Cricinfo", _fetch_espn_rss),
                                  ("Cricbuzz", _fetch_cricbuzz_live)):
        try:
            data = fetcher()
            if data:                       # empty result → try next source
                cache.set(cache_key, data, CACHE_TIMEOUT)
                matches = _enrich_live(data)
                broadcast_live(matches, f"✅ Data from {source_label}")
                return matches, f"✅ Data from {source_label}"
        except Exception as e:
            print(f"[LIVE SCORES] {source_label} fetch failed: {e}")

    return [], "⚠️ Live feeds are temporarily unavailable — please try again in a moment"


def _enrich_live(matches):
    """Tag league + float live IPL games to the top."""
    for m in matches:
        m.setdefault('league', classify_match(m.get('title')))
    return sorted(matches, key=lambda m: (not m.get('is_live'), m.get('league') != 'IPL'))


def _fetch_espn_rss():
    """ESPN Cricinfo's free RSS feed of live scores (standard RSS 2.0 XML).

    Item titles look like: "West Indies 250/8  v England 230 *"
    (the trailing * marks the match still in progress)."""
    if not HAS_SCRAPER:
        return None
    resp = requests.get(ESPN_LIVE_RSS_URL, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    matches = []
    for item in root.findall('.//channel/item')[:8]:
        title = (item.findtext('title') or '').strip()
        if not title:
            continue
        guid = (item.findtext('guid') or '').strip()
        href = (item.findtext('link') or guid).strip()

        m = re.search(r'/match/(\d+)\.html', guid)
        match_id = f"espn-{m.group(1)}" if m else ''

        # "TeamA 250/8  v TeamB 230 *" → ["TeamA 250/8", "TeamB 230 *"]
        scores = [s.strip() for s in title.split(' v ')] if ' v ' in title else []

        matches.append({
            'id': match_id,
            'title': title.replace(' *', '').strip(),
            'href': href,
            'status': 'Live' if '*' in title else 'Summary',
            'is_live': '*' in title,
            'scores': scores,
        })
    return matches

def _fetch_cricbuzz_live():
    if not HAS_SCRAPER:
        return None
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
        return None


def get_match_scorecard(match_id):
    """Detailed scorecard. Chain: cache → CricZop scrape → Cricbuzz → ESPN
    summary → honest "not available" card. Never shows fake scores."""
    cache_key = f'scorecard_detail_{match_id}'

    cached = cache.get(cache_key)
    if cached:
        return cached, "✅ Data from cache (no API call used)"

    # Cheap, always-available truth for ids we already know from the live list —
    # no upstream call needed, so it never trips the rate gate.
    summary = _summary_card(match_id)

    can_call, message = check_api_rate_limit()
    if not can_call:
        if summary:
            return summary, "📡 Live score from ESPN Cricinfo (full card coming soon)"
        return None, message or "⏳ Refreshing — try again in a moment"

    for source_label, fetcher in (("CricZop", _fetch_criczop_card),
                                  ("Cricbuzz", _fetch_match_scorecard)):
        try:
            data = fetcher(match_id)
            if data and data.get('innings'):
                cache.set(cache_key, data, CACHE_TIMEOUT)
                return data, f"✅ Data from {source_label}"
        except Exception as e:
            print(f"[SCORECARD] {source_label} fetch failed: {e}")

    if summary:
        return summary, "📡 Live score from ESPN Cricinfo (full card coming soon)"
    return None, "⚠️ Full scorecard isn't available for this match yet — please try again in a moment"


def _summary_card(match_id):
    """Last-resort REAL (not demo) card: innings totals parsed from the live list."""
    for m in cache.get('cricbuzz_live_matches') or []:
        if str(m.get('id')) == str(match_id):
            title = m['title']
            parts = [s.strip() for s in title.split(' v ')]
            innings = []
            for i, side in enumerate(parts):
                # side like "Malaysia 144/6" or "United Arab Emirates 150/4 *"
                team = re.sub(r'\s+\d+/\d+.*$', '', side).strip() or side
                runs = re.search(r'(\d+/\d+(?:\s*\([\d.]+\))?)', side)
                innings.append({'title': f'{team} — Innings {i+1}', 'batsmen': [],
                                'total': runs.group(1).replace(' ', '') if runs else side})
            return {'match_title': title.replace(' *', '').strip(),
                    'status': m.get('status', 'Live'),
                    'innings': innings, 'source_url': m.get('href', '')}
    return None

_ACRONYMS = {
    'wi': 'windies', 'nz': 'new zealand', 'sa': 'south africa',
    'sl': 'sri lanka', 'uae': 'united arab emirates', 'eng': 'england',
    'aus': 'australia', 'ind': 'india', 'pak': 'pakistan', 'ban': 'bangladesh',
    'afg': 'afghanistan', 'zim': 'zimbabwe', 'ire': 'ireland', 'ned': 'netherlands',
}


def _criczop_url_for(match_id):
    """Map our live-list match to its CricZop scorecard URL via team-name matching."""
    known = cache.get('cricbuzz_live_matches') or []
    title = next((m['title'] for m in known if str(m.get('id')) == str(match_id)), '')
    if not title:
        return None
    resp = requests.get(CRICZOP_BASE, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, 'lxml')
    words = {w for w in re.sub(r'\d+/\d+|\s+v\s+|\*', ' ', title.lower()).split()
             if len(w) > 2}                                           # team-word tokens
    words = {_ACRONYMS.get(w, w) for w in words}
    best, best_hits = None, 0
    for a in soup.select('a[href*="/live-cricket-score/"]'):
        href = a.get('href', '')
        slug = href.lower()
        hits = sum(1 for w in words if w in slug)
        if hits >= max(2, best_hits):                                # need both teams to hit
            best, best_hits = href, hits
    return CRICZOP_BASE + best if best else None


def _fetch_criczop_card(match_id):
    """CricZop server-rendered scorecard → same shape as Cricbuzz parser."""
    if not HAS_SCRAPER:
        return None
    url = _criczop_url_for(match_id)
    if not url:
        return None
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, 'lxml')

    title = soup.select_one('h1')
    rows = soup.select('.grid-cols-scoretable-bat')
    batsmen = []
    for r in rows:
        cells = [c.strip() for c in r.stripped_strings]
        if len(cells) < 6 or cells[0] == 'Player':
            continue
        name, runs, balls, fours, sixes, sr = cells[0], *cells[-5:]
        dismissal = ' '.join(cells[1:-5]) or 'not out'   # "c X b Y" can span 2 cells
        batsmen.append({'name': name, 'dismissal': dismissal, 'runs': runs,
                        'balls': balls, 'fours': fours, 'sixes': sixes, 'sr': sr})
    if not batsmen:
        return None

    total = ''
    for h in soup.select('[class*=scorecardGridTotalRuns]'):
        t = ' '.join(h.stripped_strings)
        # "Total runs 14.5/20 ov · Run Rate: 6.74 100/4" → "100/4 (14.5 Ov)"
        m = re.search(r'Total runs\s+([\d.]+)/\d+\s*ov.*?([\d]+\s*/\s*\d+)\s*$', t)
        if m:
            total = f"{m.group(2).replace(' ', '')} ({m.group(1)} Ov)"
        else:
            m2 = re.search(r'([\d]+\s*/\s*\d+)\s*$', t)
            total = m2.group(1).replace(' ', '') if m2 else t
        break
    inn = soup.select_one('[class*=scoretable-fow]')
    first_fow = ' '.join(inn.stripped_strings)[:60] if inn else ''

    return {
        'match_title': title.get_text(strip=True)[:80] if title else '',
        'status': (total or first_fow or 'Live')[:60],
        'innings': [{'title': 'Batting', 'batsmen': batsmen, 'total': total}],
        'source_url': url,
    }


def _fetch_match_scorecard(match_id):
    if not HAS_SCRAPER:
        return None
    if not str(match_id).isdigit():
        # Only Cricbuzz's own ids map to its /live-cricket-scorecard/<id> URL —
        # espn-* / non-numeric ids have no valid Cricbuzz page to hit.
        return None
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
        return None


def build_live_payload():
    """Shared payload for the HTML page and the JSON/WS updates."""
    matches, note = get_cricbuzz_live()
    ipl_live = [m for m in matches if m.get('league') == 'IPL' and m.get('is_live')]
    other = [m for m in matches if not (m.get('league') == 'IPL' and m.get('is_live'))]
    return {
        'matches': matches,
        'ipl_live': ipl_live,
        'other_matches': other,
        'has_live_ipl': bool(ipl_live),
        'next_ipl': next_ipl_window(),
        'note': note,
    }


# ── VIEWS ──

def scorecard_home(request):
    payload = build_live_payload()
    return render(request, 'scorecard/scorecard.html', {
        'matches': payload['matches'],
        'has_live_ipl': payload['has_live_ipl'],
        'next_ipl': payload['next_ipl'],
        'data_note': payload['note'],
    })


def scorecard_detail(request, match_id):
    scorecard, note = get_match_scorecard(match_id)
    return render(request, 'scorecard/scorecard_detail.html', {
        'scorecard': scorecard, 'match_id': match_id, 'data_note': note,
    })


@rate_limit([
    ('live_api:minute', getattr(settings, 'RATE_LIMITS', {}).get('live_api_minute', '30/m')),
], scope='user', message='Live score API limit reached — the page auto-refreshes for you, no need to hammer it. 🏏')
def live_matches_api(request):
    return JsonResponse(build_live_payload())


@rate_limit([
    ('live_api:minute', getattr(settings, 'RATE_LIMITS', {}).get('live_api_minute', '30/m')),
], scope='user', message='Live score API limit reached — the page auto-refreshes for you, no need to hammer it. 🏏')
def scorecard_api(request, match_id):
    scorecard, note = get_match_scorecard(match_id)
    scorecard['note'] = note
    return JsonResponse(scorecard)
