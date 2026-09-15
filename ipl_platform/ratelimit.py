"""Lightweight, dependency-free rate limiting.

Uses Django's cache framework so it works on every free tier with zero
extra services (locmem in dev / single-worker deploys, Redis if you add one).

Two scopes are enforced:
  * per-user — identified by the Django session key (no login needed),
    falling back to the client IP.
  * global   — protects shared quotas, e.g. the Groq free-tier daily cap
    that ALL users draw from.

Limits are configured in settings.py (see RATE_LIMITS) and can be raised/
lowered per deployment via environment variables.
"""
import hashlib
import time
from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse

_PERIODS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}


def _parse_rate(rate):
    """'10/m' -> (10, 60)"""
    count, _, period = rate.strip().partition('/')
    return int(count), _PERIODS[period.lstrip('per ')[:1] or 'm']


def client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def user_scope_id(request):
    """Stable anonymous user id (session key -> IP), hashed for privacy."""
    ident = ''
    try:
        if not request.session.session_key:
            request.session.create()
        ident = request.session.session_key or ''
    except Exception:
        # Read-only storage (e.g. serverless SQLite) — fall back to IP.
        ident = ''
    ident = ident or client_ip(request)
    return hashlib.sha256(ident.encode()).hexdigest()[:16]


def _hit(key, count, window):
    """Count one hit inside the current fixed window.

    Returns (allowed, remaining, reset_after_seconds). Fails OPEN if the
    cache backend is unavailable (never block users because Redis is down).
    """
    now = time.time()
    bucket = int(now // window)
    cache_key = f'rl:{key}:{bucket}'
    try:
        hits = cache.get(cache_key)
        if hits is None:
            cache.set(cache_key, 1, window + 2)
            hits = 1
        else:
            hits = cache.incr(cache_key)
    except Exception:
        return True, count, 0
    return hits <= count, max(0, count - hits), int((bucket + 1) * window - now)


def check_rate(key, rate, scope_id=None):
    """Check a single limit. Returns (allowed, remaining, reset_after)."""
    count, window = _parse_rate(rate)
    full_key = f'{key}:{scope_id}' if scope_id else key
    return _hit(full_key, count, window)


class RateLimited(Exception):
    def __init__(self, message, retry_after):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


def enforce(limits, request=None, scope='user'):
    """Enforce a list of (key, rate) limits.

    scope='user' -> one counter per anonymous user (session/IP)
    scope='global' -> single counter shared by everyone
    Raises RateLimited when any limit is exceeded.
    """
    scope_id = user_scope_id(request) if scope == 'user' and request is not None else None
    for key, rate in limits:
        allowed, _remaining, reset_after = check_rate(key, rate, scope_id)
        if not allowed:
            raise RateLimited(
                f'Rate limit reached for {key}. Please try again in {max(1, reset_after)}s.',
                reset_after,
            )


def rate_limit(limits, scope='user', message='Too many requests — please slow down.'):
    """Decorator for function views. Returns HTTP 429 (JSON) when limited.

    Usage:
        @rate_limit([('jarvis', '10/m')], scope='user')
    """
    if isinstance(limits, tuple):
        limits = [limits]

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            try:
                enforce(limits, request=request, scope=scope)
            except RateLimited as rl:
                resp = JsonResponse(
                    {'error': rl.message, 'message': message, 'retry_after': rl.retry_after},
                    status=429,
                )
                resp['Retry-After'] = str(rl.retry_after)
                return resp
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
