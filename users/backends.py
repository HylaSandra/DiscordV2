from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        identifier = username or kwargs.get(user_model.USERNAME_FIELD)
        if not identifier or not password:
            return None

        candidates = user_model._default_manager.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier)
        )
        for user in candidates:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None

