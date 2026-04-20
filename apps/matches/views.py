from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
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


def ensure_demo_matches():
    teams = {t.short_name: t for t in Team.objects.all()}
    if not teams: teams = {t.short_name: t for t in ensure_teams()}
    now = timezone.now()
    fixtures = [
        ('MI','CSK','live','Wankhede Stadium, Mumbai'),
        ('RCB','KKR','live','Eden Gardens, Kolkata'),
        ('GT','RR','upcoming','Narendra Modi Stadium, Ahmedabad'),
        ('DC','SRH','upcoming','Arun Jaitley Stadium, Delhi'),
        ('PBKS','LSG','completed','PCA Stadium, Mohali'),
        ('MI','RCB','completed','Wankhede Stadium, Mumbai'),
    ]
    for i,(t1s,t2s,status,venue) in enumerate(fixtures):
        t1 = teams.get(t1s); t2 = teams.get(t2s)
        if not t1 or not t2: continue
        cid = f'demo-{t1s}-{t2s}-2025'
        m, created = Match.objects.get_or_create(cricapi_id=cid, defaults={
            'team1':t1,'team2':t2,'venue':venue,
            'match_date': now + timedelta(hours=i*4-8),
            'status': status,
        })
        if created or m.status == 'live':
            if status == 'live':
                r = random.randint(90,175); w = random.randint(2,7)
                m.team1_score=f'{r}/{w}'; m.team1_overs=f'{round(random.uniform(8,19),1)}'
                m.last_ball_event = random.choice(['4','6','1','0','W','2'])
            elif status == 'completed':
                r1=random.randint(140,210); r2=random.randint(100,r1+15)
                m.team1_score=f'{r1}/7'; m.team1_overs='20.0'
                m.team2_score=f'{r2}/8'; m.team2_overs='20.0'
                m.result = f'{t1.name} won by {r1-r2} runs' if r1>r2 else f'{t2.name} won by 2 wickets'
            m.save()


def home(request):
    ensure_teams()
    ensure_demo_matches()
    from apps.chat.models import ChatRoom
    live = Match.objects.filter(status='live').select_related('team1','team2')
    upcoming = Match.objects.filter(status='upcoming').select_related('team1','team2')[:4]
    completed = Match.objects.filter(status='completed').select_related('team1','team2')[:4]
    teams = Team.objects.all()[:10]
    rooms = ChatRoom.objects.all()[:3]
    return render(request, 'matches/home.html', {
        'live': live, 'upcoming': upcoming, 'completed': completed, 'teams': teams, 'rooms': rooms,
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
    ensure_demo_matches()
    live = Match.objects.filter(status='live').select_related('team1','team2')
    upcoming = Match.objects.filter(status='upcoming').select_related('team1','team2')
    completed = Match.objects.filter(status='completed').select_related('team1','team2')
    return render(request, 'matches/all_matches.html', {'live':live,'upcoming':upcoming,'completed':completed})
