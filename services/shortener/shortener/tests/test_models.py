"""Module 6 model additions: tags, the owner reference, and the manager."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from ..models import URL, Tag


class URLManagerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        cls.live = URL.objects.create(original_url='https://example.com/live', owner_id=7)
        cls.future = URL.objects.create(
            original_url='https://example.com/future', expires_at=now + timedelta(days=1)
        )
        cls.expired = URL.objects.create(
            original_url='https://example.com/expired', expires_at=now - timedelta(days=1)
        )
        cls.inactive = URL.objects.create(original_url='https://example.com/off', is_active=False)

    def test_active_urls_excludes_expired_and_inactive(self):
        self.assertEqual(set(URL.objects.active_urls()), {self.live, self.future})

    def test_expired_urls_returns_only_past_expiry(self):
        self.assertEqual(list(URL.objects.expired_urls()), [self.expired])

    def test_popular_urls_orders_by_the_denormalized_counter(self):
        URL.objects.filter(pk=self.future.pk).update(click_count=5)
        URL.objects.filter(pk=self.live.pk).update(click_count=2)

        popular = list(URL.objects.popular_urls())
        self.assertEqual(popular[0], self.future)
        self.assertEqual(popular[1], self.live)

    def test_popular_urls_respects_limit(self):
        self.assertEqual(len(URL.objects.popular_urls(limit=1)), 1)

    def test_for_code_matches_short_code_or_alias(self):
        aliased = URL.objects.create(original_url='https://example.com/a', custom_alias='mylink')
        self.assertEqual(URL.objects.get_queryset().for_code('mylink').get(), aliased)
        self.assertEqual(
            URL.objects.get_queryset().for_code(self.live.short_code).get(), self.live
        )

    def test_with_related_prefetches_tags_without_n_plus_one(self):
        self.live.tags.add(Tag.objects.create(name='docs'))
        # One query for the URLs, one for the prefetched tags — and no third
        # for an owner, because the owner is not a relation any more.
        with self.assertNumQueries(2):
            for url in URL.objects.active_urls().with_related():
                list(url.tags.all())


class OwnerReferenceTests(TestCase):
    """`owner_id` is a plain integer pointing into the auth service."""

    def test_owner_id_defaults_to_null(self):
        self.assertIsNone(URL.objects.create(original_url='https://example.com').owner_id)

    def test_owner_id_accepts_an_id_with_no_matching_row_anywhere(self):
        """There is no user table here, so nothing can validate this id.

        That is the trade database-per-service makes, and pinning it here
        stops someone from "fixing" it into a ForeignKey later.
        """
        url = URL.objects.create(original_url='https://example.com', owner_id=999999)
        url.refresh_from_db()
        self.assertEqual(url.owner_id, 999999)


class TagTests(TestCase):
    def test_many_to_many_traverses_both_directions(self):
        tag = Tag.objects.create(name='marketing')
        url = URL.objects.create(original_url='https://example.com')
        url.tags.add(tag)

        self.assertEqual(list(tag.urls.all()), [url])
        self.assertEqual(list(url.tags.all()), [tag])


class ShortCodeCollisionTests(TestCase):
    @patch('shortener.models.generate_short_code')
    def test_generated_code_dodges_an_existing_custom_alias(self, generate):
        """A generated code colliding with an alias would make for_code() 500.

        It matches on either column, so two rows sharing a value turns every
        lookup of that value into MultipleObjectsReturned.
        """
        URL.objects.create(original_url='https://example.com/a', custom_alias='taken')
        generate.side_effect = ['unique']

        url = URL(original_url='https://example.com/b', short_code='taken')
        url.save()

        self.assertEqual(url.short_code, 'unique')

    @patch('shortener.models.generate_short_code')
    def test_generated_code_dodges_an_existing_short_code(self, generate):
        existing = URL.objects.create(original_url='https://example.com/a')
        generate.side_effect = ['unique']

        url = URL(original_url='https://example.com/b', short_code=existing.short_code)
        url.save()

        self.assertEqual(url.short_code, 'unique')

    def test_is_expired_property(self):
        past = URL.objects.create(
            original_url='https://example.com', expires_at=timezone.now() - timedelta(seconds=1)
        )
        never = URL.objects.create(original_url='https://example.com/2')
        self.assertTrue(past.is_expired)
        self.assertFalse(never.is_expired)
