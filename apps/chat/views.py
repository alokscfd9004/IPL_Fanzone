from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
import json
from .models import ChatRoom, ChatMessage


def chat_home(request):
    """Display all chat rooms"""
    rooms = ChatRoom.objects.all()
    return render(request, 'chat/chat.html', {'rooms': rooms})


def chat_room(request, room_name):
    """Display specific chat room"""
    room = get_object_or_404(ChatRoom, name=room_name)
    messages = room.messages.all()[:50]  # Last 50 messages
    return render(request, 'chat/chat.html', {
        'room': room,
        'messages': messages,
        'room_name': room_name
    })


def create_chat_room(request):
    """Create a new chat room"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    data = json.loads(request.body)
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    
    if not name:
        return JsonResponse({'error': 'Name required'}, status=400)
    
    room, created = ChatRoom.objects.get_or_create(
        name=name,
        defaults={'description': description}
    )
    
    return JsonResponse({
        'created': created,
        'room': {'name': room.name, 'description': room.description}
    })


def get_chat_messages(request, room_name):
    """Get messages for a room (API)"""
    room = get_object_or_404(ChatRoom, name=room_name)
    messages = room.messages.all().order_by('-created_at')[:100]
    return JsonResponse({
        'messages': [
            {
                'username': msg.username,
                'message': msg.message,
                'created_at': msg.created_at.isoformat()
            }
            for msg in messages
        ]
    })
