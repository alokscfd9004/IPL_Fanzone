"""
Comprehensive tests for Jarvis AI Bot
"""
import json
import os
from django.test import TestCase, Client, override_settings
from django.conf import settings
from pathlib import Path
from unittest.mock import patch, MagicMock
from .models import JarvisConversation, JarvisMessage
from .views import handle_commands, load_memory, save_memory


class CommandHandlerTests(TestCase):
    """Test the command handler system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.memory_file = Path(settings.JARVIS_MEMORY_FILE)
        # Clear memory before each test
        if self.memory_file.exists():
            self.memory_file.unlink()
    
    def tearDown(self):
        """Clean up after tests"""
        if self.memory_file.exists():
            self.memory_file.unlink()
    
    def test_greeting_command(self):
        """Test hello/hi command responses"""
        reply, action = handle_commands("hello")
        self.assertIsNotNone(reply)
        self.assertIn("hello", reply.lower())
        
        reply, action = handle_commands("hi")
        self.assertIsNotNone(reply)
    
    def test_exit_command(self):
        """Test exit/stop/goodbye commands"""
        reply, action = handle_commands("stop")
        self.assertIsNotNone(reply)
        self.assertEqual(action, "EXIT")
        
        reply, action = handle_commands("exit")
        self.assertIsNotNone(reply)
        self.assertEqual(action, "EXIT")
    
    def test_name_storage(self):
        """Test storing and recalling user name"""
        reply, action = handle_commands("my name is John")
        self.assertIn("John", reply)
        
        memory = load_memory()
        self.assertEqual(memory.get("name"), "John")
        
        # Recall name
        reply, action = handle_commands("what is my name")
        self.assertIn("John", reply)
    
    def test_location_storage(self):
        """Test storing and recalling location"""
        reply, action = handle_commands("i live in Mumbai")
        self.assertIn("Mumbai", reply)
        
        memory = load_memory()
        self.assertEqual(memory.get("location"), "Mumbai")
        
        # Recall location
        reply, action = handle_commands("where do i live")
        self.assertIn("Mumbai", reply)
    
    def test_who_am_i(self):
        """Test who am I command"""
        # First, set a name
        handle_commands("my name is Rajesh")
        
        reply, action = handle_commands("who am i")
        self.assertIn("Rajesh", reply)
    
    def test_search_command(self):
        """Test search command"""
        reply, action = handle_commands("search python tutorials")
        self.assertIn("searching", reply.lower())
        self.assertIsNotNone(action)
        self.assertIn("google.com", action)
    
    def test_play_command(self):
        """Test play music command"""
        reply, action = handle_commands("play imagine by john lennon")
        self.assertIn("playing", reply.lower())
        self.assertIsNotNone(action)
        self.assertIn("youtube.com", action)
    
    def test_time_command(self):
        """Test time command"""
        reply, action = handle_commands("time")
        self.assertIn("time", reply.lower())
        self.assertIsNone(action)
    
    def test_memory_persistence(self):
        """Test that memory persists across multiple calls"""
        handle_commands("my name is Alex")
        handle_commands("i live in Delhi")
        
        memory = load_memory()
        self.assertEqual(memory.get("name"), "Alex")
        self.assertEqual(memory.get("location"), "Delhi")


class MemorySystemTests(TestCase):
    """Test the memory system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.memory_file = Path(settings.JARVIS_MEMORY_FILE)
        # Clear memory before each test
        if self.memory_file.exists():
            self.memory_file.unlink()
    
    def tearDown(self):
        """Clean up after tests"""
        if self.memory_file.exists():
            self.memory_file.unlink()
    
    def test_load_empty_memory(self):
        """Test loading memory when file doesn't exist"""
        memory = load_memory()
        self.assertIsInstance(memory, dict)
        self.assertEqual(len(memory), 0)
    
    def test_save_and_load_memory(self):
        """Test saving and loading memory"""
        test_data = {"name": "Test User", "location": "Test City", "custom": "value"}
        save_memory(test_data)
        
        loaded_memory = load_memory()
        self.assertEqual(loaded_memory, test_data)
    
    def test_memory_file_creation(self):
        """Test that memory file is created"""
        test_data = {"test": "data"}
        save_memory(test_data)
        
        self.assertTrue(self.memory_file.exists())
        self.assertGreater(self.memory_file.stat().st_size, 0)


class ModelTests(TestCase):
    """Test Jarvis models"""
    
    def test_conversation_creation(self):
        """Test creating a conversation"""
        conv = JarvisConversation.objects.create(
            session_id="test_123",
            user_name="Test User",
            favorite_team="MI"
        )
        self.assertEqual(conv.user_name, "Test User")
        self.assertEqual(conv.favorite_team, "MI")
    
    def test_message_creation(self):
        """Test creating a message"""
        conv = JarvisConversation.objects.create(session_id="test_456")
        msg = JarvisMessage.objects.create(
            conversation=conv,
            role="user",
            content="Hello Jarvis"
        )
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "Hello Jarvis")
        self.assertEqual(msg.conversation, conv)
    
    def test_message_ordering(self):
        """Test messages are ordered by creation time"""
        conv = JarvisConversation.objects.create(session_id="test_789")
        
        msg1 = JarvisMessage.objects.create(
            conversation=conv,
            role="user",
            content="First message"
        )
        msg2 = JarvisMessage.objects.create(
            conversation=conv,
            role="assistant",
            content="Response"
        )
        
        messages = conv.messages.all()
        self.assertEqual(messages[0], msg1)
        self.assertEqual(messages[1], msg2)


class JarvisViewsTests(TestCase):
    """Test Jarvis views"""
    
    def setUp(self):
        """Set up test client"""
        self.client = Client()
        self.memory_file = Path(settings.JARVIS_MEMORY_FILE)
        if self.memory_file.exists():
            self.memory_file.unlink()
    
    def tearDown(self):
        """Clean up"""
        if self.memory_file.exists():
            self.memory_file.unlink()
    
    def test_jarvis_page_loads(self):
        """Test jarvis page can be accessed"""
        response = self.client.get('/jarvis/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Jarvis', response.content.decode())
    
    def test_jarvis_ask_requires_post(self):
        """Test ask endpoint requires POST"""
        response = self.client.get('/jarvis/ask/')
        self.assertEqual(response.status_code, 405)
    
    def test_jarvis_ask_empty_message(self):
        """Test ask endpoint with empty message"""
        response = self.client.post(
            '/jarvis/ask/',
            data=json.dumps({'message': '', 'history': []}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
    
    def test_jarvis_ask_with_message(self):
        """Test ask endpoint with valid message"""
        response = self.client.post(
            '/jarvis/ask/',
            data=json.dumps({'message': 'hello', 'history': []}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('response', data)
    
    def test_jarvis_memory_get(self):
        """Test memory endpoint GET"""
        response = self.client.get('/jarvis/memory/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIsInstance(data, dict)
    
    def test_jarvis_memory_post(self):
        """Test memory endpoint POST"""
        test_data = {"name": "Test", "location": "City"}
        response = self.client.post(
            '/jarvis/memory/',
            data=json.dumps(test_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify memory was saved
        response = self.client.get('/jarvis/memory/')
        data = json.loads(response.content)
        self.assertEqual(data.get("name"), "Test")


class AIIntegrationTests(TestCase):
    """Test AI integration and error handling"""
    
    def test_groq_api_key_missing_handling(self):
        """Test handling of missing GROQ_API_KEY"""
        response = Client().post(
            '/jarvis/ask/',
            data=json.dumps({'message': 'test query', 'history': []}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        # Should still return a response even if API key is missing
        self.assertIn('response', data)
    
    @patch('apps.ai_bot.views.client')
    def test_ai_response_with_history(self, mock_client):
        """Test AI response with conversation history"""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Test response"
        mock_client.chat.completions.create.return_value = mock_response
        
        response = Client().post(
            '/jarvis/ask/',
            data=json.dumps({
                'message': 'test',
                'history': [
                    {'role': 'user', 'content': 'hi'},
                    {'role': 'assistant', 'content': 'hello'}
                ]
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
