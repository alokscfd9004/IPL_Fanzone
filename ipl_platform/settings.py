import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('SECRET_KEY', 'ipl-fanzone-v2-dev-key')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['*']

# Required for POST forms (chat/Jarvis) when served over HTTPS (Vercel etc.)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]

INSTALLED_APPS = [
    # MUST be first: makes `manage.py runserver` serve ASGI (WebSockets):
    # without it, /ws/* routes 404 under plain WSGI and chat never connects.
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'corsheaders',
    'apps.matches',
    'apps.chat',
    'apps.fans',
    'apps.ai_bot',
    'apps.history',
    'apps.scorecard',
    'apps.privacy',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ipl_platform.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ipl_platform.wsgi.application'
ASGI_APPLICATION = 'ipl_platform.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# ── Cache (powers rate limiting + scraper cache; no extra service needed) ──
# Set CACHE_URL=redis://... in production to share limits across workers.
CACHES = {
    'default': {
        'BACKEND': os.getenv('CACHE_BACKEND', 'django.core.cache.backends.locmem.LocMemCache'),
        'LOCATION': os.getenv('CACHE_LOCATION', 'ipl-fanzone'),
    }
}

# ── Rate limits (ipl_platform/ratelimit.py) ──
# Format: 'count/period' where period is s(econd), m(inute), h(our), d(ay).
# Per-user limits are keyed by the anonymous session id (or IP fallback) so
# one visitor cannot burn the shared Groq free-tier quota.
RATE_LIMITS = {
    # Groq (Jarvis) — per user
    'jarvis_user_minute': os.getenv('JARVIS_RATE_PER_MINUTE', '10/m'),
    'jarvis_user_day': os.getenv('JARVIS_RATE_PER_DAY', '50/d'),
    # Groq (Jarvis) — global daily safety cap for the shared free-tier key
    'jarvis_global_day': os.getenv('JARVIS_GLOBAL_PER_DAY', '1000/d'),
    # Live-score JSON APIs — per user
    'live_api_minute': os.getenv('LIVE_API_RATE_PER_MINUTE', '30/m'),
    # Privacy endpoints — per user (export/delete shouldn't be hammered either)
    'privacy_api': os.getenv('PRIVACY_API_RATE_PER_MINUTE', '10/m'),
}

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
CORS_ALLOW_ALL_ORIGINS = True

# API Keys (Groq AI — free tier). Live scores come from free CricketData.org
# widgets + Cricbuzz scraping, so no CricAPI key is needed.
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'openai/gpt-oss-20b')

# Public site URL (used for sitemap/canonical tags)
SITE_URL = os.getenv('SITE_URL', 'http://127.0.0.1:8000')

# Memory file for Jarvis AI
JARVIS_MEMORY_FILE = BASE_DIR / 'jarvis_memory.json'

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True
