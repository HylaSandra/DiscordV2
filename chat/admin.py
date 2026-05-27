from django.contrib import admin

from .models import Channel, DirectMessageThread, Message, Reaction


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "audience", "created_by", "created_at")
    list_filter = ("kind", "audience", "created_at")
    search_fields = ("name", "description")
    filter_horizontal = ("members",)


@admin.register(DirectMessageThread)
class DirectMessageThreadAdmin(admin.ModelAdmin):
    list_display = ("user_one", "user_two", "updated_at")
    search_fields = ("user_one__username", "user_two__username")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("author", "channel", "thread", "created_at", "is_deleted")
    list_filter = ("is_deleted", "created_at")
    search_fields = ("author__username", "content")


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("user", "emoji", "message", "created_at")
    search_fields = ("user__username", "emoji")
