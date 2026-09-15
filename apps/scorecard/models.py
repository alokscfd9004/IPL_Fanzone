from django.db import models


class ScorecardCache(models.Model):
    """Cache for scraped cricbuzz scorecards"""
    match_id = models.CharField(max_length=200, unique=True)
    match_title = models.CharField(max_length=300)
    team1_name = models.CharField(max_length=100)
    team1_score = models.CharField(max_length=50, blank=True)
    team2_name = models.CharField(max_length=100)
    team2_score = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=50, default='live')
    batting_scorecard = models.JSONField(default=dict, blank=True)
    bowling_scorecard = models.JSONField(default=dict, blank=True)
    raw_html = models.TextField(blank=True)
    scraped_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.match_title}"


class Batsman(models.Model):
    """Batting scorecard details"""
    scorecard = models.ForeignKey(ScorecardCache, on_delete=models.CASCADE, related_name='batsmen')
    name = models.CharField(max_length=100)
    runs = models.IntegerField()
    balls = models.IntegerField()
    fours = models.IntegerField()
    sixes = models.IntegerField()
    status = models.CharField(max_length=50, blank=True)  # Out/Not Out

    def __str__(self):
        return f"{self.name} - {self.runs}({self.balls})"


class Bowler(models.Model):
    """Bowling scorecard details"""
    scorecard = models.ForeignKey(ScorecardCache, on_delete=models.CASCADE, related_name='bowlers')
    name = models.CharField(max_length=100)
    overs = models.CharField(max_length=10)
    runs = models.IntegerField()
    wickets = models.IntegerField()
    economy = models.FloatField()

    def __str__(self):
        return f"{self.name} - {self.wickets}/{self.runs}"
