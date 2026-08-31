from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'tier', 'is_premium', 'is_staff']
    list_filter = ['tier', 'is_premium', 'is_staff', 'is_active']
    # Required by any admin that wants to autocomplete against users, and
    # cheap insurance besides: without it Django raises admin.E040 the moment
    # another ModelAdmin adds `autocomplete_fields = ['owner']`.
    search_fields = ['username', 'email']
    fieldsets = UserAdmin.fieldsets + (
        ('Tiering', {'fields': ('is_premium', 'tier')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Tiering', {'fields': ('email', 'is_premium', 'tier')}),
    )
