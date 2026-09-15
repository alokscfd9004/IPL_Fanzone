from django.db import models


class FanProfile(models.Model):
    """Fan profile with preferences"""
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(blank=True)
    favorite_team = models.CharField(max_length=100, blank=True)
    favorite_player = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    joined_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-joined_date']

    def __str__(self):
        return self.username


class FanStats(models.Model):
    """Fan engagement statistics"""
    fan = models.OneToOneField(FanProfile, on_delete=models.CASCADE, related_name='stats')
    matches_watched = models.IntegerField(default=0)
    reactions_count = models.IntegerField(default=0)
    chat_messages_count = models.IntegerField(default=0)
    ai_interactions_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Stats for {self.fan.username}"
