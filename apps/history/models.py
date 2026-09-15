from django.db import models


class Season(models.Model):
    """IPL Season data"""
    year = models.IntegerField(unique=True, primary_key=True)
    champion = models.CharField(max_length=100)
    runner_up = models.CharField(max_length=100)
    matches = models.IntegerField()
    sixes = models.IntegerField()
    fours = models.IntegerField()
    venues = models.IntegerField()
    teams = models.IntegerField(default=8)
    half_centuries = models.IntegerField(default=0)
    centuries = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year']

    def __str__(self):
        return f"IPL {self.year} - {self.champion} won"


class SeasonDetail(models.Model):
    """Extended season statistics"""
    season = models.OneToOneField(Season, on_delete=models.CASCADE, related_name='details')
    orange_cap_player = models.CharField(max_length=100)
    orange_cap_team = models.CharField(max_length=100)
    orange_cap_runs = models.IntegerField()
    purple_cap_player = models.CharField(max_length=100)
    purple_cap_team = models.CharField(max_length=100)
    purple_cap_wickets = models.IntegerField()
    most_fours_player = models.CharField(max_length=100)
    most_fours_team = models.CharField(max_length=100)
    most_fours_count = models.IntegerField()
    most_sixes_player = models.CharField(max_length=100)
    most_sixes_team = models.CharField(max_length=100)
    most_sixes_count = models.IntegerField()

    def __str__(self):
        return f"Details for {self.season.year}"
