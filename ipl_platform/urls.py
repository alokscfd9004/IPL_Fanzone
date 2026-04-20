from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.matches.urls')),
    path('history/', include('apps.history.urls')),
    path('scorecard/', include('apps.scorecard.urls')),
    path('chat/', include('apps.chat.urls')),
    path('fans/', include('apps.fans.urls')),
    path('jarvis/', include('apps.ai_bot.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
