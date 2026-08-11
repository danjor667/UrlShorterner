from django.contrib import admin
from .models import URL


@admin.register(URL)
class URLAdmin(admin.ModelAdmin):
    list_display = ['short_code', 'custom_alias', 'original_url', 'click_count', 'is_active', 'created_at']
    search_fields = ['short_code', 'custom_alias', 'original_url']
    list_filter = ['is_active']
