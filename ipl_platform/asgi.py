import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ipl_platform.settings')

# Initialize Django BEFORE importing anything that touches models.
# get_asgi_application() calls django.setup() internally.
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
import apps.chat.routing  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(apps.chat.routing.websocket_urlpatterns)
    ),
})
