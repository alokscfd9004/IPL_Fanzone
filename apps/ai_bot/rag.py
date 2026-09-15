"""RAG (retrieval-augmented generation) for Jarvis.

Jarvis's answers are grounded in the *processed IPL ball-by-ball dataset*
(2008–2025) instead of the LLM's fuzzy memory:

  1. build_documents() converts the dataset + curated season data into a
     small corpus of fact sheets (one per season + leaderboard rollups).
  2. retrieve() ranks them for a user question with a pure-Python TF-IDF
     (no numpy/sklearn needed, so free-tier serverless deploys stay light).
  3. rag_context() formats the top-k sheets so views.ask_ai() can prepend
     them to the Groq system prompt.

Optional: if langchain-core + langchain-groq are installed (see
requirements-rag.txt) and USE_LANGCHAIN_RAG=true, the chat completion is
orchestrated through LangChain's ChatGroq instead of the raw client —
the retrieval layer stays the same fast built-in one.
"""
import math
import os
import re

from django.conf import settings
from django.core.cache import cache

_CACHE_KEY = 'rag:ipl_docs:v1'
_MAX_CHARS = 1200

_STOPWORDS = {
    'the', 'a', 'an', 'of', 'in', 'on', 'for', 'and', 'or', 'is', 'was',
    'were', 'who', 'what', 'which', 'did', 'do', 'does', 'to', 'how', 'many',
    'much', 'me', 'tell', 'show', 'give', 'ipl', 'season', 'year', 'that',
    'this', 'it', 'its', 'by', 'with', 'at', 'from', 'as', 'are', 'be', 'been',
}

WORD_RE = re.compile(r'[a-z0-9]+')


def _tokens(text):
    return [t for t in WORD_RE.findall(text.lower()) if t not in _STOPWORDS]


# ────────────────────────── corpus build ──────────────────────────

def build_documents():
    """One fact-sheet per season + all-time leaderboard rollups."""
    try:
        from apps.history.data_loader import load_processed
        from apps.history.views import IPL_SEASONS, SEASON_DETAILS
    except Exception:
        return []

    seasons, details = {}, {}
    processed = load_processed(settings.BASE_DIR)
    if processed:
        seasons, details = processed
    # curated embedded data extends/overrides the dataset (e.g. latest season)
    for y, s in IPL_SEASONS.items():
        seasons[y] = s
    for y, d in SEASON_DETAILS.items():
        details.setdefault(y, {}).update(d)

    # full name -> abbreviation map, so "csk vs srh final" matches season docs
    from apps.history.data_loader import LINEAGE, TEAM_MAP
    name_to_short = {full: short for short, full in TEAM_MAP.values()}
    for team_id, olds in LINEAGE.items():
        short = TEAM_MAP[team_id][0]
        for _until, old in olds:
            name_to_short[old] = short

    def tag(name):
        short = name_to_short.get(name)
        return f"{name} ({short})" if short else name

    docs = []
    title_count = {}
    orange_winners, purple_winners, sixes_kings = [], [], []

    for year in sorted(seasons):
        s = seasons[year]
        d = details.get(year, {})
        oc, pc = d.get('orange_cap', {}), d.get('purple_cap', {})
        m6, m4 = d.get('most_sixes', {}), d.get('most_fours', {})

        champion, runner = s.get('champion', ''), s.get('runner_up', '')
        if champion:
            title_count[champion] = title_count.get(champion, 0) + 1
        if oc.get('player'):
            orange_winners.append(f"{year}: {oc['player']} ({oc.get('team', '—')}) {oc.get('runs')} runs")
        if pc.get('player'):
            purple_winners.append(f"{year}: {pc['player']} ({pc.get('team', '—')}) {pc.get('wickets')} wickets")
        if m6.get('player'):
            sixes_kings.append(f"{year}: {m6['player']} hit the most sixes ({m6.get('count')})")

        parts = [
            f"IPL {year}: {tag(champion)} were the champions/winners — {champion} won IPL {year}.",
            f"Final: {tag(champion)} beat {tag(runner)} in the {year} final. Runner-up: {runner}.",
        ]
        if d.get('final_note'):
            parts.append(f"Final: {d['final_note']}.")
        if s.get('matches'):
            extras = [f"{s['matches']} matches"]
            if s.get('teams'):
                extras.append(f"{s['teams']} teams")
            if s.get('sixes'):
                extras.append(f"{s['sixes']} sixes and {s.get('fours')} fours")
                extras.append(f"{s.get('venues')} venues")
            parts.append("Season totals: " + ", ".join(extras) + ".")
        if oc.get('player'):
            parts.append(f"Orange Cap (most runs) {year}: {oc['player']} of {tag(oc.get('team', '—'))} with {oc.get('runs')} runs.")
        if pc.get('player'):
            parts.append(f"Purple Cap (most wickets) {year}: {pc['player']} of {tag(pc.get('team', '—'))} with {pc.get('wickets')} wickets.")
        if m6.get('player'):
            parts.append(f"Most sixes {year}: {m6['player']} ({m6.get('count')}).")
        if m4.get('player'):
            parts.append(f"Most fours {year}: {m4['player']} ({m4.get('count')}).")
        pt = d.get('points_table') or []
        if pt:
            top4 = ", ".join(f"{i+1}. {t.get('team')} ({t.get('pts')} pts)" for i, t in enumerate(pt[:4]))
            parts.append(f"Top of the {year} points table: {top4}.")

        docs.append({
            'id': f'season-{year}',
            'title': f'IPL {year} — champions, caps and records',
            'text': ' '.join(parts),
        })

    if title_count:
        tally = sorted(title_count.items(), key=lambda kv: (-kv[1], kv[0]))
        docs.append({
            'id': 'titles-all',
            'title': 'Which team has won the most IPL titles',
            'text': ('IPL titles won by each franchise (most IPL trophies): '
                     + ', '.join(f'{team} — {n}' for team, n in tally)
                     + '.'),
        })
    if seasons:
        docs.append({
            'id': 'champions-all',
            'title': 'IPL winners list 2008 onwards',
            'text': ('IPL winners list (champions year by year): '
                     + ', '.join(f'{y} {seasons[y]["champion"]}' for y in sorted(seasons))
                     + '.'),
        })
    if orange_winners:
        docs.append({
            'id': 'orange-cap-all',
            'title': 'Orange Cap winners list (most runs each IPL season)',
            'text': 'Orange Cap winners (most runs) by season: ' + '; '.join(orange_winners) + '.',
        })
    if purple_winners:
        docs.append({
            'id': 'purple-cap-all',
            'title': 'Purple Cap winners list (most wickets each IPL season)',
            'text': 'Purple Cap winners (most wickets) by season: ' + '; '.join(purple_winners) + '.',
        })
    if sixes_kings:
        docs.append({
            'id': 'sixes-all',
            'title': 'Most sixes in each IPL season',
            'text': 'Player with the most sixes per IPL season: ' + '; '.join(sixes_kings) + '.',
        })
    return docs


def _corpus_mtime():
    """Fingerprint of the source data so a re-import invalidates the cache."""
    mtimes = ['0']
    try:
        from apps.history.data_loader import processed_file_path
        fp = processed_file_path(settings.BASE_DIR)
        if fp.exists():
            mtimes.append(str(int(fp.stat().st_mtime)))
    except Exception:
        pass
    return '-'.join(mtimes)


def get_documents():
    cached = cache.get(_CACHE_KEY)
    mtime = _corpus_mtime()
    if cached and cached[0] == mtime:
        return cached[1]
    docs = build_documents()
    cache.set(_CACHE_KEY, (mtime, docs), 86_400)
    return docs


# ────────────────────────── retrieval ──────────────────────────

def retrieve(query, k=3):
    """Rank documents by TF-IDF cosine similarity. Returns [(score, doc), ...]."""
    docs = get_documents()
    if not docs or not query:
        return []

    q_tokens = _tokens(query)
    if not q_tokens:
        return []

    doc_tokens = [_tokens(d['title'] + ' ' + d['text']) for d in docs]
    n = len(docs)
    df = {}
    for toks in doc_tokens:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1

    def idf(t):
        return math.log(1.0 + n / (1.0 + df.get(t, 0)))

    q_tf = {}
    for t in q_tokens:
        q_tf[t] = q_tf.get(t, 0) + 1
    q_vec = {t: tf * idf(t) for t, tf in q_tf.items()}
    q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

    scored = []
    for doc, toks in zip(docs, doc_tokens):
        if not toks:
            continue
        d_tf = {}
        for t in toks:
            d_tf[t] = d_tf.get(t, 0) + 1
        dot, d_norm = 0.0, 0.0
        for t, qv in q_vec.items():
            dv = d_tf.get(t, 0) * idf(t)
            dot += qv * dv
        for t, tf in d_tf.items():
            v = tf * idf(t)
            d_norm += v * v
        d_norm = math.sqrt(d_norm) or 1.0
        score = dot / (q_norm * d_norm)
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: -x[0])
    return scored[:k]


def rag_context(query, k=3, max_chars=_MAX_CHARS):
    """Formatted retrieval result ready to append to the LLM system prompt."""
    hits = retrieve(query, k=k)
    if not hits:
        return ''
    parts = []
    total = 0
    for _score, doc in hits:
        chunk = f"• {doc['title']}: {doc['text']}"
        if total + len(chunk) > max_chars:
            chunk = chunk[:max_chars - total].rstrip() + '…'
        parts.append(chunk)
        total += len(chunk)
        if total >= max_chars:
            break
    return 'Verified IPL records relevant to this question (trust these over training-data memory):\n' + '\n'.join(parts)


# ─────────────────── offline answer engine (no LLM call) ───────────────────

_YEAR_RE = re.compile(r'\b((?:19|20)\d{2})\b')
# TF-IDF score needed before we answer straight from a fact-sheet (no Groq).
# Measured on this corpus: true hits score ~0.42–0.65, noise ~0.05–0.2.
_HIGH_CONFIDENCE = 0.40


def _latest(seasons):
    return max(seasons) if seasons else None


def local_answer(query):
    """Answer directly from the verified dataset — no Groq call, no quota.

    Returns a reply string, or None when confidence is too low (caller then
    falls through to the LLM path).
    """
    docs = get_documents()
    if not docs:
        return None

    low = query.lower()
    year_match = _YEAR_RE.search(query)
    doc_by_id = {d['id']: d for d in docs}

    def sheet(doc_id):
        d = doc_by_id.get(doc_id)
        return d['text'] if d else None

    def target_year():
        if year_match:
            y = int(year_match.group(1))
            if f'season-{y}' in doc_by_id:
                return y
        return _latest([int(d['id'].split('-')[1]) for d in docs if d['id'].startswith('season-')])

    wants = lambda *words: any(w in low for w in words)
    y = target_year()

    # ── predictions & opinions need the LLM, not the record book ──
    if wants('predict', 'prediction', 'who will win', 'will win', 'next ipl',
             'next match', 'who is better', "who's better", 'best ever', 'goat'):
        return None

    # ── title counts / winner lists across history (no single season) ──
    if not year_match:
        if wants('most title', 'most troph', 'most ipl', 'how many title',
                 'how many troph', 'how many ipl'):
            text = sheet('titles-all')
            if text:
                return "🏆 " + text
        if wants('winner list', 'champions list', 'all champions', 'all winners',
                 'winners of all', 'ipl champions', 'every winner', 'each year',
                 'every year', 'year by year', 'all ipl winner'):
            text = sheet('champions-all')
            if text:
                return "📜 " + text

    if y is None:
        # No season context at all — try high-confidence TF-IDF fallback
        hits = retrieve(query, k=1)
        if hits and hits[0][0] >= _HIGH_CONFIDENCE:
            d = hits[0][1]
            return f"📚 {d['text']}"
        return None

    text = sheet(f'season-{y}')
    if not text:
        return None

    # ── per-season intents, answered from the fact-sheet ──
    keymap = [
        (('orange cap', 'most runs', 'highest run', 'top scorer', 'top run'),
         'orange cap', '🟠'),
        (('purple cap', 'most wickets', 'highest wicket', 'top wicket', 'top bowler'),
         'purple cap', '🟣'),
        (('most sixes', 'maximum sixes', 'sixes king'),
         'most sixes', '💥'),
        (('most fours', 'most boundaries'),
         'most fours', '🏏'),
    ]
    sentences = [s.strip() for s in text.split('. ') if s.strip()]
    for triggers, marker, emoji in keymap:
        if wants(*triggers):
            for s in sentences:
                if marker in s.lower():
                    return f"{emoji} {s}."
    if wants('won', 'win', 'winner', 'champion', 'trophy', 'title', 'beat', 'final', 'result'):
        # first two sentences are always the champion + final sentence
        return f"🏆 {sentences[0]}. {sentences[1]}"
    if wants('points table', 'standings', 'top 4', 'top four', 'table top', 'league stage'):
        for s in sentences:
            if 'points table' in s.lower():
                return f"📊 {s}."
    if wants('how many matches', 'number of matches', 'total matches'):
        for s in sentences:
            if 'season totals' in s.lower() or 'matches' in s.lower():
                return f"🏟 {s}."

    # ── generic: high-confidence TF-IDF or nothing ──
    hits = retrieve(query, k=1)
    if hits and hits[0][0] >= _HIGH_CONFIDENCE:
        d = hits[0][1]
        return f"📚 {d['text']}"
    return None

def use_langchain():
    """True when the operator opted in AND the extra packages are installed."""
    if os.getenv('USE_LANGCHAIN_RAG', 'false').lower() not in ('1', 'true', 'yes'):
        return False
    try:
        import langchain_groq  # noqa: F401
        import langchain_core  # noqa: F401
        return True
    except ImportError:
        return False


def langchain_chat(system_prompt, history, question, model, api_key):
    """Same RAG, orchestrated via LangChain's ChatGroq chain."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_groq import ChatGroq

    llm = ChatGroq(model=model, api_key=api_key, max_tokens=500, temperature=0.75)
    messages = [SystemMessage(content=system_prompt)]
    for h in (history or [])[-6:]:
        cls = HumanMessage if h.get('role') == 'user' else AIMessage
        messages.append(cls(content=h.get('content', '')))
    messages.append(HumanMessage(content=question))
    return llm.invoke(messages).content
