from django.db.models import Count

from chat.models import Channel, DirectMessageThread


def global_navigation(request):
    if not request.user.is_authenticated:
        return {}

    text_channels = Channel.objects.filter(
        members=request.user,
        kind=Channel.KIND_TEXT,
    ).order_by("name")
    voice_channels = Channel.objects.filter(
        members=request.user, kind=Channel.KIND_VOICE
    ).annotate(
        active_voice_count=Count("active_voice_users", distinct=True)
    ).order_by("name")
    dm_threads = DirectMessageThread.objects.for_user(request.user)
    unread_items = request.user.notifications.filter(is_read=False)
    unread_notifications = unread_items.count()
    unread_channel_ids = list(
        unread_items.filter(channel__isnull=False)
        .values_list("channel_id", flat=True)
        .distinct()
    )
    unread_thread_ids = list(
        unread_items.filter(thread__isnull=False)
        .values_list("thread_id", flat=True)
        .distinct()
    )

    return {
        "nav_text_channels": text_channels[:8],
        "nav_voice_channels": voice_channels[:8],
        "nav_dm_threads": dm_threads[:8],
        "unread_notifications_count": unread_notifications,
        "unread_channel_ids": unread_channel_ids,
        "unread_thread_ids": unread_thread_ids,
    }
