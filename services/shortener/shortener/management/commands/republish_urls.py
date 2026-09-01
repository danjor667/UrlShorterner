"""Resend every URL to the analytics projection.

The projection is maintained by best-effort publishes, so any analytics outage
leaves it behind. Nothing retries automatically until Module 8 puts these on a
task queue, which makes this the manual repair tool in the meantime.

Safe to run at any time: the receiving endpoint upserts by `url_id`.
"""

from django.core.management.base import BaseCommand

from shortener.events import publish_url_upsert
from shortener.models import URL


class Command(BaseCommand):
    help = 'Republish every URL to the analytics service projection.'

    def handle(self, *args, **options):
        published = failed = 0
        for url in URL.objects.all().iterator():
            if publish_url_upsert(url):
                published += 1
            else:
                failed += 1

        self.stdout.write(f'published {published}')
        if failed:
            raise SystemExit(self.style.ERROR(f'{failed} failed — see the log and retry'))
        self.stdout.write(self.style.SUCCESS('projection is in sync'))
