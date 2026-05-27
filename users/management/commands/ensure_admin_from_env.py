import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Creates or updates an admin account from environment variables."

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip().lower()
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")

        if not username or not email or not password:
            self.stdout.write(
                self.style.WARNING(
                    "Skipping admin bootstrap because DJANGO_SUPERUSER_* variables are not fully set."
                )
            )
            return

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )

        updates = []
        if user.email != email:
            user.email = email
            updates.append("email")
        if not user.is_staff:
            user.is_staff = True
            updates.append("is_staff")
        if not user.is_superuser:
            user.is_superuser = True
            updates.append("is_superuser")
        if getattr(user, "role", "") != user_model.ROLE_ADMIN:
            user.role = user_model.ROLE_ADMIN
            updates.append("role")

        user.set_password(password)
        updates.append("password")
        user.save(update_fields=updates)

        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Created admin user '{username}'.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Updated admin user '{username}'.")
            )
