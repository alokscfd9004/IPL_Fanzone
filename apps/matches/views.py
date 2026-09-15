from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
import json, random
from .models import Match, Team, Reaction, FanInsight


TEAM_DATA = [
    ('Mumbai Indians','MI','#004BA0','#FFFFFF','🔵','Wankhede Stadium'),
    ('Chennai Super Kings','CSK','#FDB913','#005DA0','🦁','MA Chidambaram Stadium'),
    ('Royal Challengers Bengaluru','RCB','#EC1C24','#000000','🦅','M. Chinnaswamy Stadium'),
    ('Kolkata Knight Riders','KKR','#3A225D','#FFD700','⚡','Eden Gardens'),
    ('Sunrisers Hyderabad','SRH','#FF822A','#000000','🌟','Rajiv Gandhi Stadium'),
    ('Rajasthan Royals','RR','#EA1A85','#254AA5','💎','Sawai Mansingh Stadium'),
    ('Punjab Kings','PBKS','#ED1B24','#A7A9AC','👑','PCA Stadium'),
    ('Delhi Capitals','DC','#00008B','#EF1B23','🦅','Arun Jaitley Stadium'),
    ('Gujarat Titans','GT','#1C1C6B','#C8C8C8','🦁','Narendra Modi Stadium'),
    ('Lucknow Super Giants','LSG','#002147','#A0E4FF','🌊','Ekana Stadium'),
]


def ensure_teams():
    teams = []
    for name,short,cp,cs,emoji,ground in TEAM_DATA:
        t,_ = Team.objects.get_or_create(short_name=short, defaults={
            'name':name,'color_primary':cp,'color_secondary':cs,
            'logo_emoji':emoji,'home_ground':ground})
        teams.append(t)
    return teams


def home(request):
    ensure_teams()
    from apps.chat.models import ChatRoom
    from apps.scorecard.views import get_cricbuzz_live, next_ipl_window

    live = Match.objects.filter(status='live').select_related('team1','team2')
    upcoming = Match.objects.filter(status='upcoming').select_related('team1','team2')[:4]
    completed = Match.objects.filter(status='completed').select_related('team1','team2')[:4]
    teams = Team.objects.all()[:10]
    rooms = ChatRoom.objects.all()[:3]

    # Real live feed (ESPN RSS → Cricbuzz) — cached, at most one upstream
    # fetch every 90 s, so the home page costs nothing extra on repeat visits.
    ext_matches, feed_note = get_cricbuzz_live()
    has_live_ipl = any(m.get('league') == 'IPL' and m.get('is_live') for m in ext_matches)
    total_live = live.count() + sum(1 for m in ext_matches if m.get('is_live'))

    return render(request, 'matches/home.html', {
        'live': live, 'upcoming': upcoming, 'completed': completed,
        'teams': teams, 'rooms': rooms,
        'ext_matches': ext_matches[:6],
        'feed_note': feed_note,
        'has_live_ipl': has_live_ipl,
        'total_live': total_live,
        'next_ipl': next_ipl_window(),
    })


def match_detail(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    rxn = {t: match.reactions.filter(reaction_type=t).count() for t,_ in Reaction.TYPES}
    insights = match.insights.all()[:20]
    return render(request, 'matches/match_detail.html', {
        'match': match, 
        'reactions': rxn,
        'insights': insights
    })


def match_live_api(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    rxn = {t: match.reactions.filter(reaction_type=t).count() for t,_ in Reaction.TYPES}
    
    # Simulate live commentary and running state
    comm_options = [
        "What a stunning delivery! Just misses the off stump.",
        "Beautifully played through the covers for a couple.",
        "The crowd is absolutely roaring for the home team!",
        "Strategic timeout taken by the bowling side.",
        "Excellent running between the wickets, turning one into two."
    ]
    running_options = ["Pitching outside off", "Short and wide", "Good length delivery", "Yorker length!"]
    
    return JsonResponse({
        'status': match.status,
        'team1': {'name':match.team1.short_name,'score':match.team1_score,'overs':match.team1_overs,'color':match.team1.color_primary},
        'team2': {'name':match.team2.short_name,'score':match.team2_score,'overs':match.team2_overs,'color':match.team2.color_primary},
        'last_event': match.last_ball_event,
        'commentary': random.choice(comm_options),
        'running': random.choice(running_options),
        'result': match.result,
        'reactions': rxn,
    })


def add_reaction(request, match_id):
    if request.method != 'POST': return JsonResponse({'error':'POST only'},status=405)
    match = get_object_or_404(Match, id=match_id)
    data = json.loads(request.body)
    rtype = data.get('reaction','fire')
    username = data.get('username','Anonymous')
    Reaction.objects.create(match=match, reaction_type=rtype, username=username)
    return JsonResponse({'count': match.reactions.filter(reaction_type=rtype).count()})


def add_insight(request, match_id):
    if request.method != 'POST': return JsonResponse({'error':'POST only'},status=405)
    match = get_object_or_404(Match, id=match_id)
    data = json.loads(request.body)
    content = data.get('content', '')
    username = data.get('username', 'Anonymous')
    team_id = data.get('team_id')
    is_tactical = data.get('is_tactical', False)
    
    team = None
    if team_id:
        team = Team.objects.filter(id=team_id).first()
        
    insight = FanInsight.objects.create(
        match=match, team=team, username=username, 
        content=content, is_tactical=is_tactical
    )
    return JsonResponse({
        'id': insight.id,
        'username': insight.username,
        'content': insight.content,
        'team_short': team.short_name if team else None,
        'created_at': insight.created_at.strftime('%H:%M')
    })


def get_insights(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    insights = match.insights.all()[:20]
    data = [{
        'username': i.username,
        'content': i.content,
        'team': i.team.short_name if i.team else None,
        'is_tactical': i.is_tactical,
        'upvotes': i.upvotes,
        'created_at': i.created_at.strftime('%H:%M')
    } for i in insights]
    return JsonResponse({'insights': data})


def all_matches(request):
    from apps.scorecard.views import get_cricbuzz_live, next_ipl_window
    live = Match.objects.filter(status='live').select_related('team1','team2')
    upcoming = Match.objects.filter(status='upcoming').select_related('team1','team2')
    completed = Match.objects.filter(status='completed').select_related('team1','team2')

    # Real live cricket (ESPN RSS) — no extra upstream cost; shared 30-min cache.
    ext_matches, feed_note = get_cricbuzz_live()
    has_live_ipl = any(m.get('league') == 'IPL' and m.get('is_live') for m in ext_matches)

    return render(request, 'matches/all_matches.html', {
        'live': live, 'upcoming': upcoming, 'completed': completed,
        'ext_matches': ext_matches,
        'feed_note': feed_note,
        'has_live_ipl': has_live_ipl,
        'next_ipl': next_ipl_window(),
    })


# ── SEO helpers ──
def robots_txt(request):
    base = f"{request.scheme}://{request.get_host()}"
    return HttpResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /chat/api/\n"
        "Disallow: /fans/api/\n"
        f"Sitemap: {base}/sitemap.xml\n",
        content_type="text/plain",
    )


def sitemap_xml(request):
    base = getattr(settings, 'SITE_URL', '') or f"{request.scheme}://{request.get_host()}"
    paths = [
        ('', 'daily', '1.0'),
        ('/matches/', 'hourly', '0.9'),
        ('/scorecard/', 'hourly', '0.9'),
        ('/history/', 'weekly', '0.8'),
        ('/jarvis/', 'weekly', '0.7'),
        ('/chat/', 'daily', '0.6'),
        ('/fans/', 'weekly', '0.5'),
    ]
    urls = ''.join(
        f'  <url><loc>{base}{p}</loc><changefreq>{cf}</changefreq><priority>{pr}</priority></url>\n'
        for p, cf, pr in paths
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'
    return HttpResponse(xml, content_type="application/xml")
