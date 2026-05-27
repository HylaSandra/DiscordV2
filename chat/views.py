from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Notification
from users.models import User

from .forms import ChannelForm, MessageForm
from .models import Channel, DirectMessageThread, Message, Reaction
from .services import (
    broadcast_group_event,
    broadcast_voice_event,
    create_channel_membership_notification,
    create_notifications_for_message,
    serialize_message,
)


def ensure_member_access(user, channel):
    if channel.is_banned(user):
        raise PermissionDenied(
            "Jesteś zablokowana lub zablokowany na tym kanale. Skontaktuj się z moderatorem kanału."
        )
    if not channel.can_access(user):
        raise PermissionDenied("Najpierw dołącz do kanału.")
    if user.is_currently_blocked:
        raise PermissionDenied("To konto jest zablokowane.")


def ensure_channel_management_access(user, channel):
    if not channel.user_can_manage_members(user):
        raise PermissionDenied(
            "Tylko właściciel kanału, moderator kanału lub administrator może zarządzać uczestnikami."
        )


def ensure_channel_role_access(user, channel):
    if not channel.user_can_assign_moderators(user):
        raise PermissionDenied(
            "Tylko właściciel kanału lub administrator może zarządzać moderatorami kanału."
        )


def json_message_error(message, status=400, field_errors=None):
    payload = {"ok": False, "error": message}
    if field_errors:
        payload["errors"] = field_errors
    return JsonResponse(payload, status=status)


def visible_channels_for_user(user):
    queryset = (
        Channel.objects.all()
        .select_related("created_by")
        .prefetch_related("members", "moderators", "banned_users")
    )
    if user.can_administer:
        return queryset
    return (
        queryset.filter(
            Q(audience=Channel.AUDIENCE_PUBLIC)
            | Q(created_by=user)
            | Q(moderators=user)
            | Q(members=user)
        )
        .exclude(banned_users=user)
        .distinct()
    )


def manageable_channels_for_user(user):
    queryset = (
        Channel.objects.all()
        .select_related("created_by")
        .prefetch_related("members", "moderators", "banned_users")
    )
    if user.can_administer:
        return queryset
    return queryset.filter(Q(created_by=user) | Q(moderators=user)).distinct()


def sort_channel_users(channel, users):
    moderator_ids = set(channel.moderators.values_list("pk", flat=True))
    sorted_users = sorted(
        list(users),
        key=lambda member: (
            0 if member.pk == channel.created_by_id else 1,
            0 if member.pk in moderator_ids else 1,
            member.username.lower(),
        ),
    )
    return sorted_users, moderator_ids


def build_channel_member_rows(channel, acting_user, users=None):
    member_source = (
        users
        if users is not None
        else channel.members.select_related("active_voice_channel").all()
    )
    ordered_users, moderator_ids = sort_channel_users(channel, member_source)
    rows = []
    for member in ordered_users:
        rows.append(
            {
                "member": member,
                "is_owner": member.pk == channel.created_by_id,
                "is_channel_moderator": member.pk in moderator_ids,
                "can_remove": channel.user_can_remove_member(acting_user, member),
                "can_ban": channel.user_can_ban_member(acting_user, member),
                "can_toggle_moderator": channel.user_can_toggle_moderator(
                    acting_user, member
                ),
            }
        )
    return rows


def build_banned_rows(channel, acting_user):
    banned_users = channel.banned_users.select_related("active_voice_channel").order_by(
        "username"
    )
    rows = []
    for member in banned_users:
        rows.append(
            {
                "member": member,
                "can_unban": channel.user_can_unban_member(acting_user, member),
            }
        )
    return rows


def build_available_users(channel, query):
    if not query:
        return []
    users = (
        User.objects.select_related("active_voice_channel")
        .exclude(pk__in=channel.members.values_list("pk", flat=True))
        .exclude(pk__in=channel.banned_users.values_list("pk", flat=True))
        .order_by("username")
    )
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(bio__icontains=query)
        )
    return users[:20]


@login_required
def dashboard(request):
    available_channels = visible_channels_for_user(request.user)
    joined_ids = set(request.user.joined_channels.values_list("id", flat=True))
    direct_threads = DirectMessageThread.objects.for_user(request.user).select_related(
        "user_one", "user_two"
    )

    return render(
        request,
        "chat/dashboard.html",
        {
            "text_channels": available_channels.filter(kind=Channel.KIND_TEXT),
            "voice_channels": available_channels.filter(kind=Channel.KIND_VOICE),
            "joined_channel_ids": joined_ids,
            "direct_threads": direct_threads,
        },
    )


@login_required
def manage_channels(request):
    channels = manageable_channels_for_user(request.user)
    channel_rows = []
    for channel in channels:
        channel_rows.append(
            {
                "channel": channel,
                "is_owner": channel.created_by_id == request.user.pk,
                "is_channel_moderator": channel.has_channel_moderator(request.user),
            }
        )

    channel_rows.sort(
        key=lambda row: (
            0 if row["is_owner"] else 1,
            0 if row["is_channel_moderator"] else 1,
            row["channel"].name.lower(),
        )
    )
    return render(
        request,
        "chat/channel_management_index.html",
        {"channel_rows": channel_rows},
    )


@login_required
def manage_channel(request, slug):
    channel = get_object_or_404(
        Channel.objects.select_related("created_by").prefetch_related(
            "members", "moderators", "banned_users"
        ),
        slug=slug,
    )
    ensure_channel_management_access(request.user, channel)

    query = request.GET.get("q", "").strip()
    member_rows = build_channel_member_rows(channel, request.user)
    banned_rows = build_banned_rows(channel, request.user)
    available_users = build_available_users(channel, query)

    return render(
        request,
        "chat/channel_management_detail.html",
        {
            "channel": channel,
            "member_rows": member_rows,
            "banned_rows": banned_rows,
            "available_users": available_users,
            "query": query,
            "can_assign_channel_moderators": channel.user_can_assign_moderators(
                request.user
            ),
        },
    )


@login_required
def create_channel(request):
    form = ChannelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        channel = form.save(commit=False)
        channel.created_by = request.user
        channel.save()
        channel.members.add(request.user)
        messages.success(
            request,
            "Kanał został utworzony. Możesz teraz zarządzać jego uczestnikami i moderatorami w zakładce Kanały.",
        )
        return redirect(channel.get_absolute_url())
    return render(request, "chat/channel_form.html", {"form": form})


@login_required
def join_channel(request, slug):
    channel = get_object_or_404(Channel, slug=slug)
    if request.user.is_currently_blocked:
        raise PermissionDenied("To konto jest zablokowane.")
    if channel.is_banned(request.user):
        raise PermissionDenied(
            "Jesteś zablokowana lub zablokowany na tym kanale. Skontaktuj się z moderatorem kanału."
        )
    if channel.members.filter(pk=request.user.pk).exists():
        return redirect(channel.get_absolute_url())
    if (
        channel.audience == Channel.AUDIENCE_GROUP
        and not channel.user_can_manage_members(request.user)
    ):
        raise PermissionDenied(
            "To kanał grupowy. Właściciel lub moderator kanału musi dodać Cię do listy uczestników."
        )
    channel.members.add(request.user)
    messages.success(request, f"Dołączono do kanału {channel.name}.")
    return redirect(channel.get_absolute_url())


def build_chat_context(
    request,
    messages_qs,
    post_url,
    read_url,
    websocket_path,
    title,
    subtitle,
    participant_rows,
    message_form,
    conversation_type,
    room_label,
    room_badge=None,
    viewer_can_moderate_messages=False,
    manage_url=None,
):
    payload = [serialize_message(message, request.user) for message in messages_qs]
    chat_page_data = {
        "postUrl": post_url,
        "readUrl": read_url,
        "websocketPath": websocket_path,
        "viewerId": request.user.pk,
        "viewerCanModerateMessages": viewer_can_moderate_messages,
        "chatType": conversation_type,
    }
    return {
        "chat_title": title,
        "chat_subtitle": subtitle,
        "chat_room_label": room_label,
        "chat_room_badge": room_badge,
        "participant_rows": participant_rows,
        "message_form": message_form,
        "messages_payload": payload,
        "chat_page_data": chat_page_data,
        "chat_manage_url": manage_url,
    }


@login_required
def channel_detail(request, slug):
    channel = get_object_or_404(
        Channel.objects.select_related("created_by").prefetch_related(
            "members", "moderators"
        ),
        slug=slug,
        kind=Channel.KIND_TEXT,
    )
    ensure_member_access(request.user, channel)
    request.user.notifications.filter(channel=channel, is_read=False).update(is_read=True)

    messages_qs = (
        channel.messages.select_related("author")
        .prefetch_related("reactions")
        .order_by("created_at")
    )
    participant_rows = build_channel_member_rows(channel, request.user)
    context = build_chat_context(
        request,
        messages_qs,
        post_url=channel.get_absolute_url() + "post/",
        read_url=channel.get_absolute_url() + "read/",
        websocket_path=f"/ws/channel/{channel.slug}/",
        title=f"#{channel.name}",
        subtitle=channel.description
        or "Kanał tekstowy z historią rozmowy i załącznikami.",
        participant_rows=participant_rows,
        message_form=MessageForm(channel=channel),
        conversation_type="channel",
        room_label=channel.get_kind_display(),
        room_badge=channel.get_audience_display(),
        viewer_can_moderate_messages=channel.user_can_moderate_messages(request.user),
        manage_url=(
            reverse("chat:manage_channel", args=[channel.slug])
            if channel.user_can_manage_members(request.user)
            else ""
        ),
    )
    context["channel"] = channel
    return render(request, "chat/conversation.html", context)


@login_required
def thread_detail(request, pk):
    thread = get_object_or_404(
        DirectMessageThread.objects.select_related("user_one", "user_two"), pk=pk
    )
    if not thread.has_participant(request.user):
        raise PermissionDenied("To nie jest Twój wątek prywatny.")
    if request.user.is_currently_blocked:
        raise PermissionDenied("To konto jest zablokowane.")
    request.user.notifications.filter(thread=thread, is_read=False).update(is_read=True)

    other = thread.other_participant(request.user)
    messages_qs = (
        thread.messages.select_related("author")
        .prefetch_related("reactions")
        .order_by("created_at")
    )
    participant_rows = [
        {
            "member": request.user,
            "is_owner": False,
            "is_channel_moderator": False,
        },
        {
            "member": other,
            "is_owner": False,
            "is_channel_moderator": False,
        },
    ]
    context = build_chat_context(
        request,
        messages_qs,
        post_url=thread.get_absolute_url() + "post/",
        read_url=thread.get_absolute_url() + "read/",
        websocket_path=f"/ws/dm/{thread.pk}/",
        title=other.username,
        subtitle=f"Wiadomości prywatne z {other.username}",
        participant_rows=participant_rows,
        message_form=MessageForm(thread=thread),
        conversation_type="direct",
        room_label="Wiadomości prywatne",
        room_badge="DM",
        viewer_can_moderate_messages=False,
    )
    context["thread"] = thread
    context["other_user"] = other
    return render(request, "chat/conversation.html", context)


@login_required
def start_thread(request, username):
    if request.user.is_currently_blocked:
        raise PermissionDenied("To konto jest zablokowane.")
    target = get_object_or_404(request.user.__class__, username=username)
    if target == request.user:
        messages.info(request, "Nie możesz otworzyć wiadomości prywatnej z samą sobą.")
        return redirect("users:directory")
    thread, _ = DirectMessageThread.get_or_create_thread(request.user, target)
    return redirect(thread.get_absolute_url())


def build_voice_room_context(request, channel, mode):
    active_rows = build_channel_member_rows(
        channel,
        request.user,
        users=channel.active_voice_users.select_related("active_voice_channel").all(),
    )
    active_participants = [row["member"] for row in active_rows]
    return {
        "channel": channel,
        "active_participant_rows": active_rows,
        "voice_room_data": {
            "mode": mode,
            "websocketPath": f"/ws/voice/{channel.slug}/",
            "viewerId": request.user.pk,
            "viewerName": request.user.username,
            "viewerAvatar": request.user.avatar_url,
            "ownerId": channel.created_by_id,
            "moderatorIds": list(channel.moderators.values_list("pk", flat=True)),
            "iceServers": settings.RTC_ICE_SERVERS,
            "initialParticipants": [
                {
                    "id": participant.pk,
                    "username": participant.username,
                    "avatar_url": participant.avatar_url,
                }
                for participant in active_participants
            ],
        },
        "chat_manage_url": (
            reverse("chat:manage_channel", args=[channel.slug])
            if channel.user_can_manage_members(request.user)
            else ""
        ),
    }


@login_required
def voice_room(request, slug):
    channel = get_object_or_404(
        Channel.objects.select_related("created_by").prefetch_related(
            "members", "moderators"
        ),
        slug=slug,
        kind=Channel.KIND_VOICE,
    )
    ensure_member_access(request.user, channel)
    context = build_voice_room_context(request, channel, mode="preview")
    return render(request, "chat/voice_room.html", context)


@login_required
def voice_session(request, slug):
    return redirect("chat:voice_room", slug=slug)


@login_required
@require_POST
def add_channel_member(request, slug):
    channel = get_object_or_404(
        Channel.objects.select_related("created_by").prefetch_related(
            "members", "moderators"
        ),
        slug=slug,
    )
    ensure_channel_management_access(request.user, channel)

    member = get_object_or_404(User, pk=request.POST.get("member_id"))
    if channel.is_banned(member):
        messages.error(
            request,
            f"Użytkownik {member.username} jest zablokowany na tym kanale. Najpierw go odbanuj.",
        )
    elif channel.members.filter(pk=member.pk).exists():
        messages.info(request, f"Użytkownik {member.username} już jest na tym kanale.")
    else:
        channel.members.add(member)
        messages.success(
            request, f"Dodano użytkownika {member.username} do kanału {channel.name}."
        )
    return redirect(reverse("chat:manage_channel", args=[channel.slug]))


@login_required
@require_POST
def remove_channel_member(request, slug, user_id):
    channel = get_object_or_404(
        Channel.objects.select_related("created_by").prefetch_related(
            "members", "moderators"
        ),
        slug=slug,
    )
    ensure_channel_management_access(request.user, channel)
    member = get_object_or_404(request.user.__class__, pk=user_id)

    if not channel.user_can_remove_member(request.user, member):
        messages.error(request, "Nie możesz usunąć tego użytkownika z kanału.")
        return redirect(reverse("chat:manage_channel", args=[channel.slug]))

    if channel.kind == Channel.KIND_VOICE:
        member.__class__.objects.filter(
            pk=member.pk,
            active_voice_channel=channel,
        ).update(active_voice_channel=None, last_seen=timezone.now())

    channel.moderators.remove(member)
    channel.members.remove(member)
    create_channel_membership_notification(channel, request.user, member)

    revocation_payload = {
        "targetUserId": member.pk,
        "target": member.pk,
        "actorName": request.user.username,
        "channelName": channel.name,
        "redirectUrl": reverse("chat:dashboard"),
    }
    broadcast_group_event(
        channel.group_name(),
        "membership_revoked",
        revocation_payload,
    )
    if channel.kind == Channel.KIND_VOICE:
        broadcast_voice_event(
            f"voice_{channel.slug}",
            "membership_revoked",
            revocation_payload,
        )
    messages.success(
        request,
        f"Usunięto użytkownika {member.username} z kanału {channel.name}.",
    )
    return redirect(reverse("chat:manage_channel", args=[channel.slug]))


@login_required
@require_POST
def ban_channel_member(request, slug, user_id):
    channel = get_object_or_404(
        Channel.objects.select_related("created_by").prefetch_related(
            "members", "moderators", "banned_users"
        ),
        slug=slug,
    )
    ensure_channel_management_access(request.user, channel)
    member = get_object_or_404(request.user.__class__, pk=user_id)

    if not channel.user_can_ban_member(request.user, member):
        messages.error(request, "Nie możesz zablokować tego użytkownika na kanale.")
        return redirect(reverse("chat:manage_channel", args=[channel.slug]))

    if channel.kind == Channel.KIND_VOICE:
        member.__class__.objects.filter(
            pk=member.pk,
            active_voice_channel=channel,
        ).update(active_voice_channel=None, last_seen=timezone.now())

    channel.moderators.remove(member)
    channel.members.remove(member)
    channel.banned_users.add(member)
    Notification.objects.create(
        recipient=member,
        actor=request.user,
        verb="zablokował Cię",
        channel=channel,
    )

    revocation_payload = {
        "targetUserId": member.pk,
        "target": member.pk,
        "actorName": request.user.username,
        "channelName": channel.name,
        "redirectUrl": reverse("chat:dashboard"),
    }
    broadcast_group_event(
        channel.group_name(),
        "channel_banned",
        revocation_payload,
    )
    if channel.kind == Channel.KIND_VOICE:
        broadcast_voice_event(
            f"voice_{channel.slug}",
            "channel_banned",
            revocation_payload,
        )

    messages.success(
        request,
        f"Zablokowano użytkownika {member.username} na kanale {channel.name}.",
    )
    return redirect(reverse("chat:manage_channel", args=[channel.slug]))


@login_required
@require_POST
def unban_channel_member(request, slug, user_id):
    channel = get_object_or_404(
        Channel.objects.select_related("created_by").prefetch_related(
            "members", "moderators", "banned_users"
        ),
        slug=slug,
    )
    ensure_channel_management_access(request.user, channel)
    member = get_object_or_404(request.user.__class__, pk=user_id)

    if not channel.user_can_unban_member(request.user, member):
        messages.error(request, "Nie możesz odbanować tego użytkownika na kanale.")
        return redirect(reverse("chat:manage_channel", args=[channel.slug]))

    channel.banned_users.remove(member)
    Notification.objects.create(
        recipient=member,
        actor=request.user,
        verb="odblokował Cię",
        channel=channel,
    )
    messages.success(
        request,
        f"Odbanowano użytkownika {member.username} na kanale {channel.name}.",
    )
    return redirect(reverse("chat:manage_channel", args=[channel.slug]))


@login_required
@require_POST
def toggle_channel_moderator(request, slug, user_id):
    channel = get_object_or_404(
        Channel.objects.select_related("created_by").prefetch_related(
            "members", "moderators"
        ),
        slug=slug,
    )
    ensure_channel_role_access(request.user, channel)
    member = get_object_or_404(request.user.__class__, pk=user_id)

    if not channel.user_can_toggle_moderator(request.user, member):
        messages.error(
            request, "Nie możesz zmienić uprawnień moderatora dla tego użytkownika."
        )
        return redirect(reverse("chat:manage_channel", args=[channel.slug]))

    if channel.moderators.filter(pk=member.pk).exists():
        channel.moderators.remove(member)
        messages.success(
            request,
            f"Usunięto uprawnienia moderatora kanału użytkownikowi {member.username}.",
        )
    else:
        channel.moderators.add(member)
        messages.success(
            request,
            f"Nadano uprawnienia moderatora kanału użytkownikowi {member.username}.",
        )
    return redirect(reverse("chat:manage_channel", args=[channel.slug]))


@login_required
@require_POST
def mark_channel_read(request, slug):
    channel = get_object_or_404(Channel, slug=slug, kind=Channel.KIND_TEXT)
    ensure_member_access(request.user, channel)
    updated = request.user.notifications.filter(channel=channel, is_read=False).update(
        is_read=True
    )
    return JsonResponse({"ok": True, "updated": updated})


@login_required
@require_POST
def mark_thread_read(request, pk):
    thread = get_object_or_404(
        DirectMessageThread.objects.select_related("user_one", "user_two"), pk=pk
    )
    if not thread.has_participant(request.user):
        return json_message_error("Brak dostępu do rozmowy.", status=403)
    updated = request.user.notifications.filter(thread=thread, is_read=False).update(
        is_read=True
    )
    return JsonResponse({"ok": True, "updated": updated})


def json_error(form):
    form_errors = form.errors.get_json_data()
    non_field_errors = form.non_field_errors()
    default_message = (
        non_field_errors[0]
        if non_field_errors
        else "Nie udało się przetworzyć formularza wiadomości."
    )
    return json_message_error(default_message, status=400, field_errors=form_errors)


@login_required
@require_POST
def post_channel_message(request, slug):
    channel = get_object_or_404(Channel, slug=slug)
    if request.user.is_currently_blocked:
        return json_message_error("To konto jest zablokowane.", status=403)
    if channel.is_banned(request.user):
        return json_message_error(
            "Jesteś zablokowana lub zablokowany na tym kanale.",
            status=403,
        )
    if not channel.can_access(request.user):
        return json_message_error("Najpierw dołącz do kanału.", status=403)
    form = MessageForm(request.POST, request.FILES, channel=channel)
    if not form.is_valid():
        return json_error(form)

    message = form.save(commit=False)
    message.author = request.user
    message.channel = channel
    message.save()

    payload = serialize_message(message, request.user)
    create_notifications_for_message(message)
    broadcast_group_event(channel.group_name(), "message_created", payload)
    return JsonResponse({"ok": True, "message": payload})


@login_required
@require_POST
def post_thread_message(request, pk):
    thread = get_object_or_404(
        DirectMessageThread.objects.select_related("user_one", "user_two"), pk=pk
    )
    if request.user.is_currently_blocked:
        return json_message_error("To konto jest zablokowane.", status=403)
    if not thread.has_participant(request.user):
        return json_message_error("Brak dostępu do rozmowy.", status=403)

    form = MessageForm(request.POST, request.FILES, thread=thread)
    if not form.is_valid():
        return json_error(form)

    message = form.save(commit=False)
    message.author = request.user
    message.thread = thread
    message.save()

    payload = serialize_message(message, request.user)
    create_notifications_for_message(message)
    broadcast_group_event(thread.group_name(), "message_created", payload)
    return JsonResponse({"ok": True, "message": payload})


@login_required
@require_POST
def edit_message(request, pk):
    message_obj = get_object_or_404(
        Message.objects.select_related("author", "channel", "thread"), pk=pk
    )
    if request.user.is_currently_blocked:
        return json_message_error("To konto jest zablokowane.", status=403)
    if message_obj.channel and not (
        message_obj.channel.can_access(request.user)
        or message_obj.channel.user_can_moderate_messages(request.user)
    ):
        return json_message_error("Nie masz dostępu do tego kanału.", status=403)

    is_author = request.user.pk == message_obj.author_id
    can_edit = is_author or (
        message_obj.channel
        and message_obj.channel.user_can_moderate_messages(request.user)
    )
    if not can_edit:
        if message_obj.thread_id:
            return json_message_error(
                "W wiadomości prywatnej możesz edytować tylko własne wiadomości.",
                status=403,
            )
        return json_message_error("Nie możesz edytować tej wiadomości.", status=403)

    content = request.POST.get("content", "").strip()
    if not content and not message_obj.image and not message_obj.voice_note:
        return json_message_error(
            "Treść nie może być pusta.",
            status=400,
            field_errors={"content": [{"message": "Treść nie może być pusta."}]},
        )

    message_obj.content = content
    message_obj.edited_at = timezone.now()
    message_obj.save(update_fields=["content", "edited_at", "updated_at"])
    payload = serialize_message(message_obj, request.user)
    broadcast_group_event(message_obj.group_name(), "message_updated", payload)
    return JsonResponse({"ok": True, "message": payload})


@login_required
@require_POST
def delete_message(request, pk):
    message_obj = get_object_or_404(
        Message.objects.select_related("author", "channel", "thread"), pk=pk
    )
    if request.user.is_currently_blocked:
        return json_message_error("To konto jest zablokowane.", status=403)
    if message_obj.channel and not (
        message_obj.channel.can_access(request.user)
        or message_obj.channel.user_can_moderate_messages(request.user)
    ):
        return json_message_error("Nie masz dostępu do tego kanału.", status=403)

    is_author = request.user.pk == message_obj.author_id
    can_delete = is_author or (
        message_obj.channel
        and message_obj.channel.user_can_moderate_messages(request.user)
    )
    if not can_delete:
        if message_obj.thread_id:
            return json_message_error(
                "W wiadomości prywatnej możesz usuwać tylko własne wiadomości.",
                status=403,
            )
        return json_message_error("Nie możesz usunąć tej wiadomości.", status=403)

    try:
        message_obj.delete_for_chat()
        payload = serialize_message(message_obj, request.user)
        broadcast_group_event(message_obj.group_name(), "message_deleted", payload)
        return JsonResponse({"ok": True, "message": payload})
    except DatabaseError:
        return json_message_error(
            "Nie udało się zapisać zmian w bazie podczas usuwania wiadomości.",
            status=500,
        )
    except Exception as exc:
        return json_message_error(
            f"Nie udało się usunąć wiadomości: {exc}",
            status=500,
        )


@login_required
@require_POST
def toggle_reaction(request, pk):
    message_obj = get_object_or_404(
        Message.objects.select_related("channel", "thread", "author"), pk=pk
    )
    if request.user.is_currently_blocked:
        return json_message_error("To konto jest zablokowane.", status=403)
    if message_obj.channel and message_obj.channel.is_banned(request.user):
        return json_message_error(
            "Jesteś zablokowana lub zablokowany na tym kanale.",
            status=403,
        )
    if message_obj.channel and not message_obj.channel.can_access(request.user):
        return json_message_error("Najpierw dołącz do kanału.", status=403)
    if message_obj.thread and not message_obj.thread.has_participant(request.user):
        return json_message_error("Brak dostępu do rozmowy.", status=403)
    emoji = request.POST.get("emoji", "👍").strip()[:16] or "👍"
    if emoji not in {"👍", "👎", "❤️"}:
        return json_message_error("Ta reakcja nie jest obsługiwana.", status=400)

    reaction, created = Reaction.objects.get_or_create(
        message=message_obj,
        user=request.user,
        emoji=emoji,
    )
    if not created:
        reaction.delete()

    payload = serialize_message(message_obj, request.user)
    broadcast_group_event(message_obj.group_name(), "message_updated", payload)
    return JsonResponse({"ok": True, "message": payload})
