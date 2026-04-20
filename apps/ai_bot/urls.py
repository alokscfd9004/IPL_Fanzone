from django.urls import path
from . import views

app_name = 'ai_bot'
urlpatterns = [
    path('', views.jarvis_page, name='jarvis'),
    path('ask/', views.jarvis_ask, name='ask'),
    path('memory/', views.jarvis_memory, name='memory'),
]
