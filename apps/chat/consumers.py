import asyncio
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import ChatRoom, ChatMessage


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': f'Connected to {self.room_name}'
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        username = data.get('username', 'Anonymous')
        message = data.get('message', '')
        
        # Save to database
        await self.save_message(username, message)
        
        # Broadcast to group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'username': username,
                'message': message
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'username': event['username'],
            'message': event['message']
        }))

    @sync_to_async
    def save_message(self, username, message):
        try:
            room = ChatRoom.objects.get(name=self.room_name)
            ChatMessage.objects.create(
                room=room,
                username=username,
                message=message
            )
        except ChatRoom.DoesNotExist:
            pass


class LiveScoreConsumer(AsyncWebsocketConsumer):
    """Pushes live cricket scores to connected clients.

    Serves /ws/live/. The reader loop reads the *cache-respecting* scorecard
    service (so the Cricbuzz fetcher's own 90s rate limit is never bypassed)
    and sends an update only when the payload actually changed. Views also
    broadcast to this group the moment a fresh scrape lands.

    Serverless hosts without WebSockets → the JS client falls back to
    polling /scorecard/api/live/ automatically.
    """

    GROUP = 'live_scores'
    POLL_SECONDS = 45

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()
        self._last_payload = ''
        await self.send_latest()
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def disconnect(self, close_code):
        task = getattr(self, '_poll_task', None)
        if task:
            task.cancel()
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def receive(self, text_data):
        # Clients send "ping" to force an immediate refresh
        await self.send_latest()

    async def _poll_loop(self):
        try:
            while True:
                await asyncio.sleep(self.POLL_SECONDS)
                await self.send_latest()
        except asyncio.CancelledError:
            pass

    async def send_latest(self):
        from apps.scorecard.views import get_cricbuzz_live
        try:
            matches, note = await sync_to_async(get_cricbuzz_live, thread_sensitive=True)()
            payload = json.dumps({
                'type': 'live_score_update',
                'matches': matches,
                'note': note,
            })
        except Exception:
            return
        if payload != self._last_payload:
            self._last_payload = payload
            await self.send(text_data=payload)

    async def live_score_update(self, event):
        """Broadcast hook called by views when a fresh scrape lands."""
        await self.send(text_data=json.dumps({
            'type': 'live_score_update',
            'matches': event['matches'],
            'note': event.get('note', ''),
        }))
