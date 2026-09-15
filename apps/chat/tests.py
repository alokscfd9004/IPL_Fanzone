"""WebSocket consumer tests (live-score push + chat)"""
import unittest


class LiveScoreConsumerTests(unittest.IsolatedAsyncioTestCase):
    """Real websocket round-trip through the full ASGI stack."""

    async def test_connect_pushes_latest_scores(self):
        from channels.testing import WebsocketCommunicator
        from ipl_platform.asgi import application

        comm = WebsocketCommunicator(application, '/ws/live/')
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        try:
            msg = await comm.receive_json_from(timeout=30)
            self.assertEqual(msg['type'], 'live_score_update')
            self.assertIn('matches', msg)
            self.assertIn('note', msg)
        finally:
            await comm.disconnect()

    async def test_chat_room_still_connects(self):
        from channels.testing import WebsocketCommunicator
        from ipl_platform.asgi import application

        comm = WebsocketCommunicator(application, '/ws/chat/general/')
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        try:
            hello = await comm.receive_json_from(timeout=10)
            self.assertEqual(hello['type'], 'connection_established')
        finally:
            await comm.disconnect()
