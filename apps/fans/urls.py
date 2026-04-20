from django.urls import path
from . import views
app_name = 'fans'
urlpatterns = [
    path('', views.fans_home, name='home'),
    path('profile/<str:username>/', views.fan_profile, name='profile'),
    path('api/create/', views.create_fan_profile, name='create'),
    path('api/update/<str:username>/', views.update_fan_profile, name='update'),
    path('api/all/', views.get_all_fans, name='all'),
]
