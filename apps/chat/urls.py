from django.urls import path
from . import views
app_name = 'chat'
urlpatterns = [
    path('', views.chat_home, name='home'),
    path('room/<str:room_name>/', views.chat_room, name='room'),
    path('api/create/', views.create_chat_room, name='create'),
    path('api/messages/<str:room_name>/', views.get_chat_messages, name='messages'),
]
