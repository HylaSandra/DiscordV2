from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class User(AbstractUser):
    ROLE_ADMIN = "administrator"
    ROLE_MODERATOR = "moderator"
    ROLE_USER = "user"
    ROLE_CHOICES = (
        (ROLE_ADMIN, "Administrator"),
        (ROLE_MODERATOR, "Moderator"),
        (ROLE_USER, "Użytkownik"),
    )

    STATUS_ONLINE = "online"
    STATUS_OFFLINE = "offline"
    STATUS_AWAY = "away"
    STATUS_CHOICES = (
        (STATUS_ONLINE, "Online"),
        (STATUS_OFFLINE, "Offline"),
        (STATUS_AWAY, "Away"),
    )

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default=ROLE_USER)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.CharField(max_length=255, blank=True, validators=[MinLengthValidator(0)])
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_OFFLINE
    )
    last_seen = models.DateTimeField(blank=True, null=True)
    is_blocked = models.BooleanField(default=False)
    blocked_until = models.DateTimeField(blank=True, null=True)
    active_voice_channel = models.ForeignKey(
        "chat.Channel",
        on_delete=models.SET_NULL,
        related_name="active_voice_users",
        blank=True,
        null=True,
        limit_choices_to={"kind": "voice"},
    )

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        if self.is_superuser and self.role != self.ROLE_ADMIN:
            self.role = self.ROLE_ADMIN
        super().save(*args, **kwargs)

    @property
    def can_administer(self) -> bool:
        return self.role == self.ROLE_ADMIN or self.is_superuser

    @property
    def can_moderate(self) -> bool:
        return self.can_administer or self.role == self.ROLE_MODERATOR

    @property
    def is_currently_blocked(self) -> bool:
        if not self.is_blocked:
            return False
        if self.blocked_until and self.blocked_until <= timezone.now():
            self.is_blocked = False
            self.blocked_until = None
            self.save(update_fields=["is_blocked", "blocked_until"])
            return False
        return True

    @property
    def effective_status(self) -> str:
        if self.active_voice_channel_id:
            return self.STATUS_ONLINE
        if self.last_seen and timezone.now() - self.last_seen > timedelta(minutes=5):
            return self.STATUS_OFFLINE
        return self.status

    @property
    def avatar_url(self) -> str:
        if self.avatar:
            return self.avatar.url
        return ""

    @property
    def voice_presence_text(self) -> str:
        if not self.active_voice_channel_id:
            return ""
        return f"Na kanale głosowym: {self.active_voice_channel.name}"

    def get_absolute_url(self):
        return reverse("users:directory")

    def __str__(self) -> str:
        return self.username


class UserReport(models.Model):
    REASON_SPAM = "spam"
    REASON_HARASSMENT = "harassment"
    REASON_ABUSE = "abuse"
    REASON_IMPERSONATION = "impersonation"
    REASON_INAPPROPRIATE = "inappropriate"
    REASON_OTHER = "other"
    REASON_CHOICES = (
        (REASON_SPAM, "Spam"),
        (REASON_HARASSMENT, "Nękanie"),
        (REASON_ABUSE, "Obraźliwe zachowanie"),
        (REASON_IMPERSONATION, "Podszywanie się"),
        (REASON_INAPPROPRIATE, "Nieodpowiednie treści"),
        (REASON_OTHER, "Inny powód"),
    )

    STATUS_NEW = "new"
    STATUS_REVIEWING = "reviewing"
    STATUS_ACTION_TAKEN = "action_taken"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_NEW, "Nowe"),
        (STATUS_REVIEWING, "W trakcie"),
        (STATUS_ACTION_TAKEN, "Podjęto działanie"),
        (STATUS_REJECTED, "Odrzucone"),
    )

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submitted_user_reports",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reported_user_reports",
    )
    reason = models.CharField(max_length=24, choices=REASON_CHOICES)
    description = models.TextField()
    status = models.CharField(
        max_length=24, choices=STATUS_CHOICES, default=STATUS_NEW
    )
    moderator_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_user_reports",
        blank=True,
        null=True,
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def clean(self):
        if self.reporter_id and self.target_user_id and self.reporter_id == self.target_user_id:
            raise ValidationError("Nie możesz zgłosić samej siebie lub samego siebie.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_resolved(self) -> bool:
        return self.status in {self.STATUS_ACTION_TAKEN, self.STATUS_REJECTED}

    def get_absolute_url(self):
        return reverse("users:reports")

    def __str__(self) -> str:
        return f"{self.reporter} -> {self.target_user} ({self.get_reason_display()})"
