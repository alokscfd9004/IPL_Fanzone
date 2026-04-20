from django.core.management.base import BaseCommand
from apps.matches.views import ensure_teams, ensure_demo_matches

class Command(BaseCommand):
    help = 'Seed demo IPL 2025 data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Creating teams...')
        ensure_teams()
        self.stdout.write('Creating matches...')
        ensure_demo_matches()
        self.stdout.write(self.style.SUCCESS('\n✅ Demo data seeded!\n\nRun: python manage.py runserver\nOpen: http://127.0.0.1:8000'))
