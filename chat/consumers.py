from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from .models import Channel, DirectMessageThread


class ChannelConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        if not self.user.is_authenticated or not await self.user_can_access():
            await self.close()
            return
        self.group_name = f"channel_{self.slug}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("action") == "ping":
            await self.send_json({"event": "pong"})

    async def chat_event(self, event):
        await self.send_json({"event": event["event_name"], "payload": event["payload"]})

    @database_sync_to_async
    def user_can_access(self):
        channel = Channel.objects.get(slug=self.slug)
        return channel.can_access(self.user) and not self.user.is_currently_blocked


class DirectMessageConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.thread_id = self.scope["url_route"]["kwargs"]["thread_id"]
        if not self.user.is_authenticated or not await self.user_can_access():
            await self.close()
            return
        self.group_name = f"dm_{self.thread_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("action") == "ping":
            await self.send_json({"event": "pong"})

    async def chat_event(self, event):
        await self.send_json({"event": event["event_name"], "payload": event["payload"]})

    @database_sync_to_async
    def user_can_access(self):
        thread = DirectMessageThread.objects.get(pk=self.thread_id)
        return thread.has_participant(self.user) and not self.user.is_currently_blocked


class VoiceSignalingConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        self.has_joined_room = False
        if not self.user.is_authenticated or not await self.user_can_access():
            await self.close()
            return

        self.room_name = f"voice_{self.slug}"
        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_name"):
            if self.has_joined_room:
                await self.clear_active_voice_channel()
                await self.channel_layer.group_send(
                    self.room_name,
                    {
                        "type": "voice.event",
                        "event_name": "participant_left",
                        "payload": {"user": await self.user_payload()},
                    },
                )
            await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        if action == "ping":
            await self.send_json({"event": "pong"})
            return

        if action == "join-room":
            await self.mark_active_voice_channel()
            self.has_joined_room = True
            await self.channel_layer.group_send(
                self.room_name,
                {
                    "type": "voice.event",
                    "event_name": "participant_joined",
                    "payload": {"user": await self.user_payload()},
                },
            )
            return

        if action in {"offer", "answer", "ice-candidate", "presence-sync"}:
            payload = {
                "from": await self.user_payload(),
                "target": content.get("target"),
                "data": content.get("data", {}),
            }
            await self.channel_layer.group_send(
                self.room_name,
                {
                    "type": "voice.event",
                    "event_name": action,
                    "payload": payload,
                },
            )

    async def voice_event(self, event):
        payload = event["payload"]
        target = payload.get("target")
        if target and target != self.user.pk:
            return
        await self.send_json({"event": event["event_name"], "payload": payload})

    @database_sync_to_async
    def user_can_access(self):
        channel = Channel.objects.get(slug=self.slug)
        return (
            channel.kind == Channel.KIND_VOICE
            and channel.can_access(self.user)
            and not self.user.is_currently_blocked
        )

    @database_sync_to_async
    def user_payload(self):
        return {
            "id": self.user.pk,
            "username": self.user.username,
            "avatar_url": self.user.avatar_url,
        }

    @database_sync_to_async
    def mark_active_voice_channel(self):
        channel = Channel.objects.get(slug=self.slug, kind=Channel.KIND_VOICE)
        self.user.__class__.objects.filter(pk=self.user.pk).update(
            active_voice_channel=channel,
            status=self.user.STATUS_ONLINE,
            last_seen=timezone.now(),
        )

    @database_sync_to_async
    def clear_active_voice_channel(self):
        self.user.__class__.objects.filter(
            pk=self.user.pk,
            active_voice_channel__slug=self.slug,
        ).update(
            active_voice_channel=None,
            last_seen=timezone.now(),
        )
