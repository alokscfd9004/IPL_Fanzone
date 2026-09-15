"""Build a fine-tuning dataset (JSONL) from the processed IPL dataset.

Generates chat-format Q&A pairs (OpenAI/Groq fine-tuning schema) from the
verified ball-by-ball data in data/ipl_processed.json + curated season data:

    {"messages": [{"role": "system", ...}, {"role": "user", ...},
                  {"role": "assistant", ...}]}

Usage:
    python manage.py build_finetune_dataset
    python manage.py build_finetune_dataset --output data/my_pairs.jsonl

NOTE: fine-tuning is OPTIONAL. Jarvis already grounds every answer with RAG
over this same data, which is free and always up to date. Fine-tune only if
you want the facts baked into a small model's weights (see README §AI).
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

SYSTEM = ("You are Jarvis, a friendly IPL cricket expert. Answer IPL history "
          "and statistics questions accurately and enthusiastically with emojis.")

SEASON_QS = [
    ("Who won IPL {y}?", "{c} won IPL {y}, beating {r} in the final! 🏆"),
    ("Which team was the IPL {y} champion?", "The IPL {y} champions were {c}. {r} finished runners-up. 🏏"),
    ("Who was the runner-up of IPL {y}?", "{r} finished runners-up in IPL {y}, losing the final to {c}."),
    ("Who won the Orange Cap in IPL {y}?", "The IPL {y} Orange Cap (most runs) went to {oc_p} of {oc_t} with {oc_r} runs. 🟠🏏"),
    ("Who had the most runs in IPL {y}?", "{oc_p} scored the most runs in IPL {y} — {oc_r} runs for {oc_t}, winning the Orange Cap. 🟠"),
    ("Who won the Purple Cap in IPL {y}?", "The IPL {y} Purple Cap (most wickets) went to {pc_p} of {pc_t} with {pc_w} wickets. 🟣🎯"),
    ("Who took the most wickets in IPL {y}?", "{pc_p} took the most wickets in IPL {y} — {pc_w} for {pc_t}, winning the Purple Cap. 🟣"),
    ("Who hit the most sixes in IPL {y}?", "{m6_p} smashed the most sixes in IPL {y} ({m6_c} maximums). 💥"),
    ("How many sixes were hit in IPL {y}?", "IPL {y} saw {sixes} sixes and {fours} fours across {matches} matches. 💥"),
    ("How many matches were played in IPL {y}?", "There were {matches} matches in IPL {y}, played at {venues} venues. 🏟"),
    ("How many centuries were scored in IPL {y}?", "IPL {y} produced {centuries} centuries and {fifties} half-centuries. 💯"),
    ("Which teams finished top of the IPL {y} points table?", "IPL {y} league-stage leaders: {top4}. 📊"),
    ("Tell me about the IPL {y} final.", "The IPL {y} final: {c} beat {r}. 🏆 Champion: {c}. Runner-up: {r}."),
]

GLOBAL_QS = [
    ("List all IPL champions year by year.", "IPL winners list: {champ_list}. 🏆"),
    ("Which team has won the most IPL titles?", "{titles_summary}. 🏆"),
    ("Who are all the Orange Cap winners in IPL history?", "Orange Cap winners (most runs) by season: {oc_list}. 🟠"),
    ("Who are all the Purple Cap winners in IPL history?", "Purple Cap winners (most wickets) by season: {pc_list}. 🟣"),
]


def _fill(tpl, **kw):
    for k, v in kw.items():
        tpl = tpl.replace('{' + k + '}', str(v))
    return tpl


def build_pairs():
    from apps.ai_bot.rag import build_documents  # noqa: F401  (ensures app data importable)
    from apps.history.data_loader import load_processed
    from apps.history.views import IPL_SEASONS, SEASON_DETAILS

    seasons, details = {}, {}
    processed = load_processed(settings.BASE_DIR)
    if processed:
        seasons, details = processed
    for y, s in IPL_SEASONS.items():
        seasons[y] = s
    for y, d in SEASON_DETAILS.items():
        details.setdefault(y, {}).update(d)

    pairs, title_count, oc_list, pc_list = [], {}, [], []

    for year in sorted(seasons):
        s = seasons[year]
        d = details.get(year, {})
        oc = d.get('orange_cap', {}) or {}
        pc = d.get('purple_cap', {}) or {}
        m6 = d.get('most_sixes', {}) or {}
        pt = d.get('points_table') or []
        champ, runner = s.get('champion', ''), s.get('runner_up', '')

        if champ:
            title_count[champ] = title_count.get(champ, 0) + 1
        if oc.get('player'):
            oc_list.append(f"{year} {oc['player']} ({oc.get('runs')} runs)")
        if pc.get('player'):
            pc_list.append(f"{year} {pc['player']} ({pc.get('wickets')} wickets)")

        kw = dict(
            y=year, c=champ, r=runner,
            matches=s.get('matches', ''), sixes=s.get('sixes', ''),
            fours=s.get('fours', ''), venues=s.get('venues', ''),
            centuries=d.get('centuries', ''), fifties=d.get('half_centuries', ''),
            oc_p=oc.get('player', '—'), oc_t=oc.get('team', '—'), oc_r=oc.get('runs', ''),
            pc_p=pc.get('player', '—'), pc_t=pc.get('team', '—'), pc_w=pc.get('wickets', ''),
            m6_p=m6.get('player', '—'), m6_c=m6.get('count', ''),
            top4=", ".join(f"{t.get('team')} ({t.get('pts')} pts)" for t in pt[:4]) or 'N/A',
        )
        for q_tpl, a_tpl in SEASON_QS:
            q, a = _fill(q_tpl, **kw), _fill(a_tpl, **kw)
            # skip pairs whose answer has unfilled placeholders or em-dash-only data
            if '{' in a or a.count('—') > 1:
                continue
            pairs.append((q, a))

    champ_list = ", ".join(f"{y} {seasons[y]['champion']}" for y in sorted(seasons))
    tally = sorted(title_count.items(), key=lambda kv: (-kv[1], kv[0]))
    gkw = dict(
        champ_list=champ_list,
        titles_summary=", ".join(f"{t} — {n} title{'s' if n != 1 else ''}" for t, n in tally),
        oc_list="; ".join(oc_list),
        pc_list="; ".join(pc_list),
    )
    for q_tpl, a_tpl in GLOBAL_QS:
        pairs.append((_fill(q_tpl, **gkw), _fill(a_tpl, **gkw)))

    return pairs


class Command(BaseCommand):
    help = 'Generate data/finetune_ipl.jsonl (chat-format fine-tuning pairs) from the processed IPL dataset'

    def add_arguments(self, parser):
        parser.add_argument('--output', default=str(Path(settings.BASE_DIR) / 'data' / 'finetune_ipl.jsonl'))

    def handle(self, *args, **options):
        pairs = build_pairs()
        out = Path(options['output'])
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, 'w') as f:
            for q, a in pairs:
                f.write(json.dumps({"messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": q},
                    {"role": "assistant", "content": a},
                ]}) + '\n')
        self.stdout.write(self.style.SUCCESS(f"✅ Wrote {len(pairs)} fine-tuning pairs → {out}"))
