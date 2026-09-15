from django.urls import path
from . import views

app_name = 'privacy'
urlpatterns = [
    path('', views.policy, name='policy'),
    path('my-data/', views.my_data, name='my_data'),
    path('export/', views.export_data, name='export'),
    path('delete/', views.delete_data, name='delete'),
    path('consent/', views.consent, name='consent'),
]
