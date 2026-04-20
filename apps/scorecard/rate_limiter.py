"""
Rate limiter for CricAPI to respect the 100 hits/day limit
Only allows 1 API call per 90 seconds
"""

import os
import time
from functools import wraps
from django.core.cache import cache

CRICAPI_RATE_LIMIT_SECONDS = 90
CRICAPI_CACHE_KEY = 'cricapi_last_request_time'

class CricAPIRateLimiter:
    """Rate limiter for CricAPI calls - max 1 request per 90 seconds"""
    
    @staticmethod
    def is_allowed():
        """Check if API call is allowed based on rate limit"""
        last_request_time = cache.get(CRICAPI_CACHE_KEY)
        
        if last_request_time is None:
            # First request
            cache.set(CRICAPI_CACHE_KEY, time.time(), CRICAPI_RATE_LIMIT_SECONDS)
            return True, 0
        
        current_time = time.time()
        time_since_last_request = current_time - last_request_time
        
        if time_since_last_request >= CRICAPI_RATE_LIMIT_SECONDS:
            # Rate limit period expired, allow request
            cache.set(CRICAPI_CACHE_KEY, current_time, CRICAPI_RATE_LIMIT_SECONDS)
            return True, 0
        else:
            # Rate limit not expired
            wait_time = CRICAPI_RATE_LIMIT_SECONDS - time_since_last_request
            return False, wait_time
    
    @staticmethod
    def get_next_available_time():
        """Get timestamp when next API request will be available"""
        last_request_time = cache.get(CRICAPI_CACHE_KEY)
        
        if last_request_time is None:
            return time.time()
        
        next_available = last_request_time + CRICAPI_RATE_LIMIT_SECONDS
        return next_available

def rate_limit_cricapi(view_func):
    """
    Decorator to rate limit CricAPI calls in views
    Only allows 1 call per 90 seconds
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        is_allowed, wait_time = CricAPIRateLimiter.is_allowed()
        
        if not is_allowed:
            # Return error response with wait time
            from django.http import JsonResponse
            return JsonResponse({
                'error': f'API rate limit exceeded. Please wait {int(wait_time)} seconds.',
                'wait_time': int(wait_time),
                'retry_after': int(wait_time)
            }, status=429)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
