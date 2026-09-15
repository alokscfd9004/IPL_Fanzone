"""GDPR / CCPA privacy app tests"""
import json
from django.test import Client, TestCase

from apps.chat.models import ChatMessage, ChatRoom


class PrivacyPageTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_policy_page(self):
        r = self.client.get('/privacy/')
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn('GDPR', body)
        self.assertIn('CCPA', body)

    def test_my_data_page(self):
        r = self.client.get('/privacy/my-data/')
        self.assertEqual(r.status_code, 200)

    def test_consent_set_and_cookie(self):
        r = self.client.post('/privacy/consent/', data=json.dumps({'choice': 'granted'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.content).get('choice'), 'granted')
        self.assertEqual(r.cookies['fz_consent'].value, 'granted')

    def test_consent_rejects_bad_choice(self):
        r = self.client.post('/privacy/consent/', data=json.dumps({'choice': 'maybe'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)


class DataRightsTests(TestCase):
    """GDPR Art. 15/17 + CCPA know/delete rights"""

    def setUp(self):
        self.client = Client()
        self.room, _ = ChatRoom.objects.get_or_create(name=f'privacy-test-{self._testMethodName}')
        ChatMessage.objects.create(room=self.room, username='ErasureFan', message='delete me later')

    def test_export_includes_my_chat_messages(self):
        r = self.client.get('/privacy/export/?username=ErasureFan')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers['Content-Disposition'].startswith('attachment'))
        data = json.loads(r.content)
        msgs = data['data']['records']['chat_messages']
        self.assertTrue(any('delete me later' in m['message'] for m in msgs))

    def test_delete_wipes_my_records_and_session(self):
        r = self.client.post('/privacy/delete/', data=json.dumps({'username': 'ErasureFan'}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        result = json.loads(r.content)
        self.assertTrue(result['ok'])
        self.assertGreaterEqual(result['deleted']['chat_messages'], 1)
        self.assertEqual(ChatMessage.objects.filter(username='ErasureFan').count(), 0)

    def test_declined_consent_blocks_jarvis_memory_persistence(self):
        self.client.cookies.load({'fz_consent': 'denied'})
        r = self.client.post('/jarvis/memory/', data=json.dumps({'username': 'NoTrack'}),
                             content_type='application/json')
        self.assertEqual(json.loads(r.content).get('persisted'), False)
        r = self.client.get('/jarvis/memory/')
        self.assertNotEqual(json.loads(r.content).get('username'), 'NoTrack')
