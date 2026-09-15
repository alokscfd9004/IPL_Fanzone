from django.urls import path
from . import views
app_name = 'matches'
urlpatterns = [
    path('', views.home, name='home'),
    path('matches/', views.all_matches, name='all'),
    path('match/<int:match_id>/', views.match_detail, name='detail'),
    path('match/<int:match_id>/api/', views.match_live_api, name='api'),
    path('match/<int:match_id>/react/', views.add_reaction, name='react'),
    path('match/<int:match_id>/insight/', views.add_insight, name='add_insight'),
    path('match/<int:match_id>/insights/', views.get_insights, name='get_insights'),
]
