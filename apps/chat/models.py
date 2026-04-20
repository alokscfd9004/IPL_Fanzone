from django.db import models


class ChatRoom(models.Model):
    """Chat room for fan discussions"""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class ChatMessage(models.Model):
    """Individual chat messages"""
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    username = models.CharField(max_length=100)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.username}: {self.message[:50]}..."
