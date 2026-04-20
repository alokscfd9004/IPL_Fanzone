from django.db import models


class JarvisConversation(models.Model):
    """Jarvis AI conversation history"""
    session_id = models.CharField(max_length=100, unique=True)
    user_name = models.CharField(max_length=100, blank=True)
    favorite_team = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Chat with {self.user_name or 'Anonymous'}"


class JarvisMessage(models.Model):
    """Individual messages in conversation"""
    ROLE_CHOICES = [('user', 'User'), ('assistant', 'Jarvis')]
    
    conversation = models.ForeignKey(JarvisConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."
