from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, UserReport


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "role",
        "status",
        "active_voice_channel",
        "is_blocked",
        "is_staff",
        "is_superuser",
    )
    list_filter = ("role", "status", "is_blocked", "is_staff", "active_voice_channel")
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "DiscordV2",
            {
                "fields": (
                    "role",
                    "avatar",
                    "bio",
                    "status",
                    "last_seen",
                    "active_voice_channel",
                    "is_blocked",
                    "blocked_until",
                )
            },
        ),
    )


@admin.register(UserReport)
class UserReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "target_user",
        "reporter",
        "reason",
        "status",
        "reviewed_by",
        "created_at",
    )
    list_filter = ("reason", "status", "created_at")
    search_fields = (
        "target_user__username",
        "reporter__username",
        "description",
        "moderator_note",
    )
