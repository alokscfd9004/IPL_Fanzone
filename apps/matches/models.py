from django.db import models

class Team(models.Model):
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=10, unique=True)
    color_primary = models.CharField(max_length=7, default='#1a1a2e')
    color_secondary = models.CharField(max_length=7, default='#FFD700')
    logo_emoji = models.CharField(max_length=10, default='🏏')
    home_ground = models.CharField(max_length=100, blank=True)
    def __str__(self): return self.name

class Match(models.Model):
    STATUS = [('upcoming','Upcoming'),('live','Live'),('completed','Completed')]
    cricapi_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    team1 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home')
    team2 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away')
    venue = models.CharField(max_length=200)
    match_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS, default='upcoming')
    team1_score = models.CharField(max_length=50, blank=True)
    team2_score = models.CharField(max_length=50, blank=True)
    team1_overs = models.CharField(max_length=20, blank=True)
    team2_overs = models.CharField(max_length=20, blank=True)
    result = models.TextField(blank=True)
    last_ball_event = models.CharField(max_length=20, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.team1.short_name} vs {self.team2.short_name}"
    class Meta: ordering = ['-match_date']

class Reaction(models.Model):
    TYPES = [('fire','🔥'),('six','6️⃣'),('wicket','🎯'),('heart','❤️'),('wow','😮'),('sad','😢')]
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='reactions')
    reaction_type = models.CharField(max_length=20, choices=TYPES)
    username = models.CharField(max_length=50, default='Anonymous')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created_at']

class FanInsight(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='insights')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True)
    username = models.CharField(max_length=50)
    content = models.TextField()
    is_tactical = models.BooleanField(default=False)
    upvotes = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-upvotes', '-created_at']
    def __str__(self): return f"{self.username}: {self.content[:30]}"
