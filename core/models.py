from django.conf import settings
from django.db import models
from django.urls import reverse


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="generated_notifications",
    )
    verb = models.CharField(max_length=120)
    message = models.ForeignKey(
        "chat.Message",
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
    )
    channel = models.ForeignKey(
        "chat.Channel",
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
    )
    thread = models.ForeignKey(
        "chat.DirectMessageThread",
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def get_location_label(self) -> str:
        if self.channel:
            if self.message_id is None and self.thread_id is None:
                return ""
            prefix = "#" if not self.channel.is_voice else ""
            return f"na kanale {prefix}{self.channel.name}"
        if self.thread:
            return "w wiadomości prywatnej"
        return "w aplikacji"

    def get_location_badge(self) -> str:
        if self.channel:
            if self.channel.is_voice:
                return self.channel.get_audience_display()
            return f"#{self.channel.name}"
        if self.thread:
            return "Wiadomość prywatna"
        return "Aktywność"

    def get_location_meta(self) -> str:
        if self.channel:
            return self.channel.full_type_label
        if self.thread:
            return "Aktywność w wiadomości prywatnej"
        return "Aktywność systemowa"

    def get_target_url(self):
        if self.thread:
            if not self.thread.has_participant(self.recipient):
                return reverse("chat:dashboard")
            return reverse("chat:thread_detail", args=[self.thread.pk])
        if self.channel:
            if not self.channel.can_access(self.recipient):
                return reverse("chat:dashboard")
            return self.channel.get_absolute_url()
        return reverse("core:notifications")

    def __str__(self) -> str:
        return f"{self.actor} -> {self.recipient}: {self.verb}"
