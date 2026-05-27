from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from chat.models import Channel
from users.models import User

from .navigation import serialize_navigation_state
from .models import Notification


def home(request):
    if request.user.is_authenticated:
        return redirect("chat:dashboard")
    return render(request, "core/home.html")


@login_required
def search(request):
    query = request.GET.get("q", "").strip()
    users = User.objects.none()
    channels = Channel.objects.none()
    joined_channel_ids = set()

    if query:
        users = (
            User.objects.select_related("active_voice_channel")
            .filter(
                Q(username__icontains=query)
                | Q(email__icontains=query)
                | Q(bio__icontains=query)
            )
            .order_by("username")
        )
        channels = Channel.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        ).order_by("name")
        if not request.user.can_administer:
            channels = (
                channels.filter(
                    Q(audience=Channel.AUDIENCE_PUBLIC)
                    | Q(created_by=request.user)
                    | Q(moderators=request.user)
                    | Q(members=request.user)
                )
                .exclude(banned_users=request.user)
                .distinct()
            )
        joined_channel_ids = set(
            request.user.joined_channels.values_list("id", flat=True)
        )

    return render(
        request,
        "core/search_results.html",
        {
            "query": query,
            "search_users": users,
            "search_channels": channels,
            "joined_channel_ids": joined_channel_ids,
        },
    )


@login_required
def notifications(request):
    items = request.user.notifications.select_related(
        "actor", "message", "channel", "thread", "thread__user_one", "thread__user_two"
    )
    return render(request, "core/notifications.html", {"notifications": items})


def serialize_notification(item):
    return {
        "id": item.pk,
        "actorUsername": item.actor.username,
        "verb": item.verb,
        "locationLabel": item.get_location_label(),
        "locationBadge": item.get_location_badge(),
        "locationMeta": item.get_location_meta(),
        "createdAt": timezone.localtime(item.created_at).strftime("%d.%m.%Y %H:%M"),
        "isRead": item.is_read,
        "openUrl": reverse("core:notification_open", args=[item.pk]),
    }


@login_required
def notifications_feed(request):
    items = request.user.notifications.select_related(
        "actor", "message", "channel", "thread", "thread__user_one", "thread__user_two"
    )
    return JsonResponse(
        {"notifications": [serialize_notification(item) for item in items[:50]]}
    )


@login_required
def notification_open(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return redirect(notification.get_target_url())


@login_required
def ui_state(request):
    return JsonResponse(serialize_navigation_state(request.user))


def custom_404(request, exception):
    return render(request, "404.html", status=404)
