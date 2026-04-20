from django.urls import path
from . import views

app_name = 'history'
urlpatterns = [
    path('', views.history_home, name='home'),
    path('api/', views.history_api, name='api'),
    path('chart-data/', views.history_chart_data, name='chart_data'),
]
