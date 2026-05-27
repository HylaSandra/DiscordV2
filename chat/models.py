from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone


class Channel(models.Model):
    KIND_TEXT = "text"
    KIND_VOICE = "voice"
    KIND_CHOICES = (
        (KIND_TEXT, "Kanał tekstowy"),
        (KIND_VOICE, "Kanał głosowy"),
    )
    AUDIENCE_PUBLIC = "public"
    AUDIENCE_GROUP = "group"
    AUDIENCE_CHOICES = (
        (AUDIENCE_PUBLIC, "Publiczny"),
        (AUDIENCE_GROUP, "Grupowy"),
    )

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True, max_length=90, blank=True)
    description = models.CharField(max_length=255, blank=True)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default=KIND_TEXT)
    audience = models.CharField(
        max_length=16,
        choices=AUDIENCE_CHOICES,
        default=AUDIENCE_PUBLIC,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_channels",
    )
    moderators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="moderated_channels",
        blank=True,
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="joined_channels", blank=True
    )
    banned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="banned_channels",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("kind", "audience", "name")

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            index = 1
            while Channel.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                index += 1
                slug = f"{base_slug}-{index}"
            self.slug = slug
        super().save(*args, **kwargs)

    def is_owner(self, user) -> bool:
        return bool(
            user.is_authenticated
            and (user.can_administer or self.created_by_id == user.pk)
        )

    def has_channel_moderator(self, user) -> bool:
        return bool(
            user.is_authenticated and self.moderators.filter(pk=user.pk).exists()
        )

    def is_banned(self, user) -> bool:
        return bool(
            user.is_authenticated and self.banned_users.filter(pk=user.pk).exists()
        )

    def user_can_assign_moderators(self, user) -> bool:
        return self.is_owner(user)

    def user_can_manage_members(self, user) -> bool:
        return self.is_owner(user) or self.has_channel_moderator(user)

    def user_can_moderate_messages(self, user) -> bool:
        return bool(
            user.is_authenticated
            and (
                user.can_moderate
                or self.created_by_id == user.pk
                or self.has_channel_moderator(user)
            )
        )

    def user_can_remove_member(self, manager, target) -> bool:
        if not self.user_can_manage_members(manager):
            return False
        if not target.is_authenticated:
            return False
        if target.pk == self.created_by_id or target.pk == manager.pk:
            return False
        if target.can_administer and not manager.can_administer:
            return False
        if self.has_channel_moderator(target) and not self.user_can_assign_moderators(
            manager
        ):
            return False
        return self.members.filter(pk=target.pk).exists()

    def user_can_ban_member(self, manager, target) -> bool:
        if not self.user_can_manage_members(manager):
            return False
        if not target.is_authenticated:
            return False
        if target.pk == self.created_by_id or target.pk == manager.pk:
            return False
        if target.can_administer and not manager.can_administer:
            return False
        if self.has_channel_moderator(target) and not self.user_can_assign_moderators(
            manager
        ):
            return False
        return self.members.filter(pk=target.pk).exists() and not self.is_banned(target)

    def user_can_unban_member(self, manager, target) -> bool:
        if not self.user_can_manage_members(manager):
            return False
        if not target.is_authenticated:
            return False
        if target.pk == self.created_by_id:
            return False
        if target.can_administer and not manager.can_administer:
            return False
        return self.is_banned(target)

    def user_can_toggle_moderator(self, manager, target) -> bool:
        if not self.user_can_assign_moderators(manager):
            return False
        if target.pk == self.created_by_id:
            return False
        if target.can_administer and not manager.can_administer:
            return False
        return self.members.filter(pk=target.pk).exists()

    def is_visible_to(self, user) -> bool:
        if not user.is_authenticated:
            return False
        if self.is_banned(user) and not self.is_owner(user):
            return False
        if self.audience == self.AUDIENCE_PUBLIC:
            return True
        return self.can_access(user)

    def can_access(self, user) -> bool:
        if not user.is_authenticated:
            return False
        if self.is_banned(user) and not self.is_owner(user):
            return False
        return (
            self.is_owner(user)
            or self.has_channel_moderator(user)
            or self.members.filter(pk=user.pk).exists()
        )

    def get_absolute_url(self):
        if self.kind == self.KIND_VOICE:
            return reverse("chat:voice_room", args=[self.slug])
        return reverse("chat:channel_detail", args=[self.slug])

    @property
    def is_voice(self) -> bool:
        return self.kind == self.KIND_VOICE

    @property
    def is_text(self) -> bool:
        return self.kind == self.KIND_TEXT

    @property
    def audience_label(self) -> str:
        return self.get_audience_display()

    @property
    def full_type_label(self) -> str:
        return f"{self.get_kind_display()} {self.get_audience_display().lower()}"

    def group_name(self) -> str:
        return f"channel_{self.slug}"

    def __str__(self) -> str:
        return self.name


class DirectMessageThreadQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(Q(user_one=user) | Q(user_two=user)).order_by("-updated_at")


class DirectMessageThread(models.Model):
    user_one = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="direct_threads_started",
    )
    user_two = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="direct_threads_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DirectMessageThreadQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user_one", "user_two"), name="unique_direct_message_thread"
            )
        ]
        ordering = ("-updated_at",)

    def clean(self):
        if self.user_one == self.user_two:
            raise ValidationError(
                "Wątek prywatny musi łączyć dwóch różnych użytkowników."
            )

    def save(self, *args, **kwargs):
        if self.user_one_id and self.user_two_id and self.user_one_id > self.user_two_id:
            self.user_one_id, self.user_two_id = self.user_two_id, self.user_one_id
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_thread(cls, user_a, user_b):
        first, second = sorted([user_a, user_b], key=lambda user: user.pk or 0)
        return cls.objects.get_or_create(user_one=first, user_two=second)

    def other_participant(self, user):
        return self.user_two if self.user_one == user else self.user_one

    def has_participant(self, user) -> bool:
        return user in [self.user_one, self.user_two]

    def group_name(self) -> str:
        return f"dm_{self.pk}"

    def get_absolute_url(self):
        return reverse("chat:thread_detail", args=[self.pk])

    def __str__(self) -> str:
        return f"{self.user_one} / {self.user_two}"


class Message(models.Model):
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        related_name="messages",
        blank=True,
        null=True,
    )
    thread = models.ForeignKey(
        DirectMessageThread,
        on_delete=models.CASCADE,
        related_name="messages",
        blank=True,
        null=True,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    content = models.TextField(blank=True)
    image = models.ImageField(upload_to="messages/images/", blank=True, null=True)
    voice_note = models.FileField(
        upload_to="messages/audio/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["mp3", "wav", "ogg", "webm", "m4a"])],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ("created_at",)

    def clean(self):
        if not self.channel and not self.thread:
            raise ValidationError(
                "Wiadomość musi należeć do kanału lub wątku prywatnego."
            )
        if self.channel and self.thread:
            raise ValidationError(
                "Wiadomość nie może należeć jednocześnie do kanału i rozmowy prywatnej."
            )
        if not self.content and not self.image and not self.voice_note:
            raise ValidationError("Wiadomość nie może być pusta.")

    def delete_for_chat(self):
        now = timezone.now()
        self.__class__.objects.filter(pk=self.pk).update(
            content="Ta wiadomość została usunięta.",
            image=None,
            voice_note=None,
            is_deleted=True,
            updated_at=now,
        )
        self.content = "Ta wiadomość została usunięta."
        self.image = None
        self.voice_note = None
        self.is_deleted = True
        self.updated_at = now
        self.touch_thread()

    def touch_thread(self):
        if self.thread:
            DirectMessageThread.objects.filter(pk=self.thread_id).update(
                updated_at=self.updated_at
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self.touch_thread()

    def group_name(self) -> str:
        return self.channel.group_name() if self.channel else self.thread.group_name()

    def __str__(self) -> str:
        target = self.channel.name if self.channel else self.thread
        return f"{self.author} -> {target}"


class Reaction(models.Model):
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="reactions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_reactions",
    )
    emoji = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("message", "user", "emoji"), name="unique_message_reaction"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} {self.emoji}"
