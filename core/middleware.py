from datetime import timedelta

from django.utils import timezone


class ActiveUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            now = timezone.now()
            updates = {}
            if user.status != user.STATUS_ONLINE:
                updates["status"] = user.STATUS_ONLINE
            if not user.last_seen or now - user.last_seen > timedelta(seconds=45):
                updates["last_seen"] = now
            if updates:
                user.__class__.objects.filter(pk=user.pk).update(**updates)
        return response

