from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.urls import reverse
from django.utils import timezone

from core.models import Notification


def serialize_message(message, viewer=None):
    reaction_summary = {}
    for reaction in message.reactions.order_by("emoji", "user__username").values(
        "emoji", "user_id", "user__username"
    ):
        bucket = reaction_summary.setdefault(
            reaction["emoji"],
            {
                "emoji": reaction["emoji"],
                "count": 0,
                "reactor_ids": [],
                "reactor_names": [],
            },
        )
        bucket["count"] += 1
        bucket["reactor_ids"].append(reaction["user_id"])
        bucket["reactor_names"].append(reaction["user__username"])

    return {
        "id": message.pk,
        "content": message.content,
        "created_at": timezone.localtime(message.created_at).strftime("%d.%m.%Y %H:%M"),
        "edited_at": (
            timezone.localtime(message.edited_at).strftime("%d.%m.%Y %H:%M")
            if message.edited_at
            else None
        ),
        "is_deleted": message.is_deleted,
        "image_url": message.image.url if message.image else None,
        "voice_url": message.voice_note.url if message.voice_note else None,
        "author": {
            "id": message.author_id,
            "username": message.author.username,
            "role": message.author.get_role_display(),
            "avatar_url": message.author.avatar_url,
            "status": message.author.effective_status,
        },
        "reactions": [
            reaction_summary[key]
            for key in sorted(reaction_summary.keys())
        ],
        "edit_url": reverse("chat:edit_message", args=[message.pk]),
        "delete_url": reverse("chat:delete_message", args=[message.pk]),
        "reaction_url": reverse("chat:toggle_reaction", args=[message.pk]),
    }


def broadcast_group_event(group_name, event_name, payload):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "chat.event",
            "event_name": event_name,
            "payload": payload,
        },
    )


def broadcast_voice_event(room_name, event_name, payload):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        room_name,
        {
            "type": "voice.event",
            "event_name": event_name,
            "payload": payload,
        },
    )


def create_notifications_for_message(message):
    recipients = []
    if message.channel:
        recipients = list(message.channel.members.exclude(pk=message.author_id))
    elif message.thread:
        recipients = [
            participant
            for participant in [message.thread.user_one, message.thread.user_two]
            if participant.pk != message.author_id
        ]

    Notification.objects.bulk_create(
        [
            Notification(
                recipient=recipient,
                actor=message.author,
                verb="wysłał nową wiadomość",
                message=message,
                channel=message.channel,
                thread=message.thread,
            )
            for recipient in recipients
        ]
    )


def create_channel_membership_notification(channel, actor, recipient):
    Notification.objects.create(
        recipient=recipient,
        actor=actor,
        verb="usunął Cię z kanału",
        channel=channel,
    )
