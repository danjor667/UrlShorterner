from django.contrib import admin

from .models import URL, Tag


@admin.register(URL)
class URLAdmin(admin.ModelAdmin):
    # No `owner` column and no autocomplete for it: the owner is an id in the
    # auth service's database, so the admin cannot resolve it to a username
    # without a cross-service call.
    list_display = ['short_code', 'custom_alias', 'original_url', 'owner_id', 'click_count',
                    'is_active', 'created_at']
    search_fields = ['short_code', 'custom_alias', 'original_url']
    list_filter = ['is_active', 'tags', 'created_at']
    filter_horizontal = ['tags']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('tags')


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']
