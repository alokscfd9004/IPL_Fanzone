from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
import json
from .models import FanProfile, FanStats


def fans_home(request):
    """Display all fan profiles"""
    fans = FanProfile.objects.filter(is_active=True)
    return render(request, 'fans/fans.html', {'fans': fans})


def fan_profile(request, username):
    """Display specific fan profile"""
    fan = get_object_or_404(FanProfile, username=username, is_active=True)
    stats = FanStats.objects.get_or_create(fan=fan)[0]
    return render(request, 'fans/fans.html', {
        'fan': fan,
        'stats': stats
    })


def create_fan_profile(request):
    """Create a new fan profile"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    data = json.loads(request.body)
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    favorite_team = data.get('favorite_team', '').strip()
    
    if not username:
        return JsonResponse({'error': 'Username required'}, status=400)
    
    try:
        fan = FanProfile.objects.create(
            username=username,
            email=email,
            favorite_team=favorite_team
        )
        FanStats.objects.create(fan=fan)
        return JsonResponse({'created': True, 'username': fan.username})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def update_fan_profile(request, username):
    """Update fan profile"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    fan = get_object_or_404(FanProfile, username=username)
    data = json.loads(request.body)
    
    fan.email = data.get('email', fan.email)
    fan.favorite_team = data.get('favorite_team', fan.favorite_team)
    fan.favorite_player = data.get('favorite_player', fan.favorite_player)
    fan.bio = data.get('bio', fan.bio)
    fan.save()
    
    return JsonResponse({'updated': True, 'username': fan.username})


def get_all_fans(request):
    """Get all fans as JSON (API)"""
    fans = FanProfile.objects.filter(is_active=True)
    return JsonResponse({
        'fans': [
            {
                'username': f.username,
                'favorite_team': f.favorite_team,
                'favorite_player': f.favorite_player,
                'bio': f.bio,
                'joined_date': f.joined_date.isoformat()
            }
            for f in fans
        ]
    })
