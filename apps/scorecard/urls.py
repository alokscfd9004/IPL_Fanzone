from django.urls import path
from . import views

app_name = 'scorecard'
urlpatterns = [
    path('', views.scorecard_home, name='home'),
    path('<str:match_id>/', views.scorecard_detail, name='detail'),
    path('api/live/', views.live_matches_api, name='live_api'),
    path('api/<str:match_id>/', views.scorecard_api, name='scorecard_api'),
]
