from django.db.models import Count

from chat.models import Channel, DirectMessageThread


def _fresh_user(user):
    return user.__class__.objects.select_related("active_voice_channel").get(pk=user.pk)


def _serialize_unread_notification(item):
    return {
        "id": item.pk,
        "actorUsername": item.actor.username,
        "verb": item.verb,
        "locationLabel": item.get_location_label(),
        "locationBadge": item.get_location_badge(),
        "channelId": item.channel_id,
        "threadId": item.thread_id,
    }


def build_navigation_context(user):
    viewer = _fresh_user(user)

    text_channels = Channel.objects.filter(
        members=viewer,
        kind=Channel.KIND_TEXT,
    ).order_by("name")
    voice_channels = Channel.objects.filter(
        members=viewer,
        kind=Channel.KIND_VOICE,
    ).annotate(
        active_voice_count=Count("active_voice_users", distinct=True)
    ).order_by("name")
    dm_threads = DirectMessageThread.objects.for_user(viewer)
    unread_items = viewer.notifications.filter(is_read=False)
    unread_preview = unread_items.select_related(
        "actor", "channel", "thread", "thread__user_one", "thread__user_two"
    )[:5]

    return {
        "viewer": viewer,
        "nav_text_channels": text_channels[:8],
        "nav_voice_channels": voice_channels[:8],
        "nav_dm_threads": dm_threads[:8],
        "unread_notifications_count": unread_items.count(),
        "unread_channel_ids": list(
            unread_items.filter(channel__isnull=False)
            .values_list("channel_id", flat=True)
            .distinct()
        ),
        "unread_thread_ids": list(
            unread_items.filter(thread__isnull=False)
            .values_list("thread_id", flat=True)
            .distinct()
        ),
        "latest_unread_notifications": [
            _serialize_unread_notification(item) for item in unread_preview
        ],
    }


def serialize_navigation_state(user):
    context = build_navigation_context(user)
    viewer = context["viewer"]

    return {
        "unreadNotificationsCount": context["unread_notifications_count"],
        "unreadChannelIds": context["unread_channel_ids"],
        "unreadThreadIds": context["unread_thread_ids"],
        "voiceChannels": [
            {
                "id": channel.id,
                "activeCount": getattr(channel, "active_voice_count", 0),
            }
            for channel in context["nav_voice_channels"]
        ],
        "activeVoiceChannel": (
            {
                "id": viewer.active_voice_channel_id,
                "name": viewer.active_voice_channel.name,
                "presenceText": viewer.voice_presence_text,
                "url": viewer.active_voice_channel.get_absolute_url(),
            }
            if viewer.active_voice_channel_id
            else None
        ),
        "effectiveStatus": viewer.effective_status,
        "roleLabel": viewer.get_role_display(),
        "latestUnreadNotifications": context["latest_unread_notifications"],
    }
