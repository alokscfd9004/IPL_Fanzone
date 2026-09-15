"""Privacy views: GDPR / CCPA transparency + data rights.

Everything is anonymous-friendly: a "user" is identified by the fan name they
typed in (stored in their own browser) and/or their Django session. No account
system exists, so export/delete work on:

  * Jarvis memory file (jarvis_memory.json)
  * JarvisConversations (+ JarvisMessages) — matched by session id / fan name
  * ChatMessages, Reactions, FanInsights, FanProfile — matched by fan name
  * the browser's localStorage — cleared client-side (we can't touch it here)
"""
import json

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from ipl_platform.ratelimit import rate_limit, user_scope_id


def _load_jarvis_memory():
    try:
        with open(settings.JARVIS_MEMORY_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _collect_user_data(username, session_id):
    """Return a dict with every piece of personal data we hold."""
    data = {
        'identity': {
            'fan_name': username or None,
            'anonymous_id': user_scope_id_hash(session_id),
        },
        'jarvis_memory': _load_jarvis_memory(),
        'records': {},
        'stored_in_your_browser (not on our servers)': [
            'fz_username (your fan name)',
            'fz_team (your favourite team)',
            'fz_consent (your cookie choice)',
        ],
    }

    if username:
        from apps.chat.models import ChatMessage
        from apps.fans.models import FanProfile
        from apps.matches.models import FanInsight, Reaction

        data['records']['chat_messages'] = list(
            ChatMessage.objects.filter(username=username)
            .values('room__name', 'message', 'created_at'))
        data['records']['reactions'] = list(
            Reaction.objects.filter(username=username)
            .values('match__id', 'reaction_type', 'created_at'))
        data['records']['fan_insights'] = list(
            FanInsight.objects.filter(username=username)
            .values('match__id', 'team__short_name', 'content', 'upvotes', 'created_at'))
        data['records']['fan_profile'] = list(
            FanProfile.objects.filter(username=username)
            .values('username', 'email', 'favorite_team', 'favorite_player', 'bio', 'joined_date'))

    # Jarvis conversation logs: match by session id and/or fan name
    from apps.ai_bot.models import JarvisConversation
    qs = JarvisConversation.objects.none()
    if session_id:
        qs = qs | JarvisConversation.objects.filter(session_id=session_id)
    if username:
        qs = qs | JarvisConversation.objects.filter(user_name=username)
    data['records']['jarvis_conversations'] = [
        {
            'started': c.created_at,
            'user_name': c.user_name,
            'messages': list(c.messages.values('role', 'content', 'created_at')),
        }
        for c in qs.distinct()[:20]
    ]
    return data


def user_scope_id_hash(session_id):
    import hashlib
    return hashlib.sha256((session_id or 'no-session').encode()).hexdigest()[:16]


def _delete_user_data(username, session_id):
    """Delete everything _collect_user_data would return. Returns counts."""
    deleted = {}
    if username:
        from apps.chat.models import ChatMessage
        from apps.fans.models import FanProfile
        from apps.matches.models import FanInsight, Reaction

        deleted['chat_messages'] = ChatMessage.objects.filter(username=username).delete()[0]
        deleted['reactions'] = Reaction.objects.filter(username=username).delete()[0]
        deleted['fan_insights'] = FanInsight.objects.filter(username=username).delete()[0]
        deleted['fan_profile'] = FanProfile.objects.filter(username=username).delete()[0]

    from apps.ai_bot.models import JarvisConversation
    qs = JarvisConversation.objects.none()
    if session_id:
        qs = qs | JarvisConversation.objects.filter(session_id=session_id)
    if username:
        qs = qs | JarvisConversation.objects.filter(user_name=username)
    pks = list(qs.distinct().values_list('pk', flat=True))
    deleted['jarvis_conversations'] = (
        JarvisConversation.objects.filter(pk__in=pks).delete()[0] if pks else 0
    )

    # Jarvis shared memory: only wipe if it belongs to this fan
    memory = _load_jarvis_memory()
    if memory and (not username or memory.get('username') in (None, '', username)):
        try:
            with open(settings.JARVIS_MEMORY_FILE, 'w') as f:
                json.dump({}, f, indent=2)
            deleted['jarvis_memory'] = 1
        except Exception:
            deleted['jarvis_memory'] = 0
    return deleted


# ────────────────────────── Pages ──────────────────────────

@require_GET
def policy(request):
    return render(request, 'privacy/policy.html')


@require_GET
def my_data(request):
    return render(request, 'privacy/my_data.html')


# ────────────────────────── Data rights API ──────────────────────────

@require_GET
@rate_limit([('privacy_api', '10/m')], scope='user')
def export_data(request):
    """GDPR Art. 15/20 & CCPA 'right to know': download all your data as JSON."""
    username = request.GET.get('username', '').strip()[:50]
    session_id = request.session.session_key or ''
    payload = {
        'about': 'IPL FanZone personal data export',
        'how_identified': 'fan name you typed + anonymous session cookie',
        'data': _collect_user_data(username, session_id),
    }
    resp = HttpResponse(
        json.dumps(payload, indent=2, default=str),
        content_type='application/json',
    )
    resp['Content-Disposition'] = 'attachment; filename="ipl_fanzone_my_data.json"'
    return resp


@require_POST
@rate_limit([('privacy_api', '10/m')], scope='user')
def delete_data(request):
    """GDPR Art. 17 & CCPA 'right to delete'."""
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        body = {}
    username = (body.get('username') or '').strip()[:50]
    session_id = request.session.session_key or ''
    deleted = _delete_user_data(username, session_id)
    try:
        request.session.flush()      # kills the session cookie's server record
    except Exception:
        pass
    resp = JsonResponse({'ok': True, 'deleted': deleted})
    # Ask the browser to drop its side too (client JS clears localStorage).
    resp.delete_cookie('fz_consent')
    return resp


@require_POST
def consent(request):
    """Store the visitor's cookie-consent choice as a first-party cookie.

    fz_consent = granted | denied  (180 days, SameSite=Lax, no tracking).
    When 'denied', the Jarvis memory endpoint stops persisting and the
    front-end skips localStorage fan-profile writes.
    """
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False}, status=400)
    choice = body.get('choice')
    if choice not in ('granted', 'denied'):
        return JsonResponse({'ok': False, 'error': 'choice must be granted|denied'}, status=400)
    resp = JsonResponse({'ok': True, 'choice': choice})
    resp.set_cookie(
        'fz_consent', choice, max_age=180 * 24 * 3600,
        samesite='Lax', secure=request.is_secure(),
    )
    return resp
