from django.core.management.base import BaseCommand
from django.conf import settings

from apps.history.data_loader import process_dataset, save_processed


class Command(BaseCommand):
    help = ("Download the Kaggle IPL dataset (slidescope/ipl-seasons-2008-to-2025) "
            "and process it into data/ipl_processed.json used by the Analysis page.")

    def handle(self, *args, **options):
        try:
            payload = process_dataset(progress=lambda m: self.stdout.write(m))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Processing failed: {e}"))
            raise SystemExit(1)

        fp = save_processed(settings.BASE_DIR, payload)
        seasons = len(payload["seasons"])
        self.stdout.write(self.style.SUCCESS(
            f"Done! {seasons} seasons processed -> {fp}"))
