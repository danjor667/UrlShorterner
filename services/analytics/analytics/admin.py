from django.contrib import admin

from .models import Click


@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    # `url_id` is a plain integer, not a relation, so there is nothing to
    # select_related and no link to follow back to the shortener.
    list_display = ['url_id', 'clicked_at', 'ip_address', 'country', 'city']
    list_filter = ['country', 'clicked_at']
    search_fields = ['url_id', 'ip_address']
    readonly_fields = ['clicked_at']
