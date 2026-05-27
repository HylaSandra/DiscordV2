from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone


@receiver(user_logged_in)
def set_online(sender, user, request, **kwargs):
    user.status = user.STATUS_ONLINE
    user.last_seen = timezone.now()
    user.save(update_fields=["status", "last_seen"])


@receiver(user_logged_out)
def set_offline(sender, user, request, **kwargs):
    if not user:
        return
    user.status = user.STATUS_OFFLINE
    user.last_seen = timezone.now()
    user.active_voice_channel = None
    user.save(update_fields=["status", "last_seen", "active_voice_channel"])
