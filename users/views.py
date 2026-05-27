from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from core.models import Notification

from .forms import (
    LoginForm,
    ProfileForm,
    RegistrationForm,
    RoleUpdateForm,
    UserReportForm,
    UserReportReviewForm,
)
from .models import User, UserReport


class CustomLoginView(LoginView):
    authentication_form = LoginForm
    template_name = "registration/login.html"


class RegisterView(CreateView):
    form_class = RegistrationForm
    template_name = "users/register.html"
    success_url = reverse_lazy("chat:dashboard")

    def form_valid(self, form):
        self.object = form.save()
        login(
            self.request,
            self.object,
            backend="users.backends.EmailOrUsernameBackend",
        )
        messages.success(self.request, "Konto zostało utworzone. Witaj w DiscordV2.")
        return redirect(self.get_success_url())


def notify_moderators_about_report(report):
    moderators = User.objects.filter(
        Q(role__in=[User.ROLE_MODERATOR, User.ROLE_ADMIN]) | Q(is_superuser=True)
    ).exclude(pk__in=[report.reporter_id, report.target_user_id])
    Notification.objects.bulk_create(
        [
            Notification(
                recipient=moderator,
                actor=report.reporter,
                verb=f"zgłosił użytkownika {report.target_user.username}",
            )
            for moderator in moderators.distinct()
        ]
    )


def notify_reporter_about_report_update(report, moderator):
    if report.reporter_id == moderator.pk:
        return
    Notification.objects.create(
        recipient=report.reporter,
        actor=moderator,
        verb=f"zaktualizował zgłoszenie dotyczące użytkownika {report.target_user.username}",
    )


def get_safe_next_url(request, default_url):
    next_url = request.POST.get("next") or request.GET.get("next") or default_url
    if next_url != default_url and not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return default_url
    return next_url


@login_required
def profile_edit(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil został zaktualizowany.")
        return redirect("users:profile")
    return render(request, "users/profile.html", {"form": form})


@login_required
def directory(request):
    query = request.GET.get("q", "").strip()
    users = User.objects.select_related("active_voice_channel").order_by("username")
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(bio__icontains=query)
        )

    directory_rows = [
        {"member": member, "role_form": RoleUpdateForm(instance=member)}
        for member in users
    ]
    return render(
        request,
        "users/directory.html",
        {
            "directory_rows": directory_rows,
            "query": query,
        },
    )


@login_required
@require_POST
def update_role(request, pk):
    if not request.user.can_administer:
        raise PermissionDenied("Tylko administrator może zmieniać role.")
    target = get_object_or_404(User, pk=pk)
    if target == request.user and request.POST.get("role") != target.role:
        messages.error(request, "Nie możesz odebrać sobie roli w tym widoku.")
        return redirect("users:directory")

    form = RoleUpdateForm(request.POST, instance=target)
    if form.is_valid():
        form.save()
        messages.success(request, f"Zmieniono rolę użytkownika {target.username}.")
    else:
        messages.error(request, "Nie udało się zaktualizować roli.")
    return redirect("users:directory")


@login_required
@require_POST
def toggle_block(request, pk):
    if not request.user.can_moderate:
        raise PermissionDenied("Brak uprawnień do blokowania użytkowników.")

    fallback_url = str(reverse_lazy("users:directory"))
    redirect_url = get_safe_next_url(request, fallback_url)
    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        messages.error(request, "Nie możesz zablokować własnego konta.")
        return redirect(redirect_url)

    if target.can_administer and not request.user.can_administer:
        messages.error(request, "Moderator nie może blokować administratora.")
        return redirect(redirect_url)

    target.is_blocked = not target.is_blocked
    if not target.is_blocked:
        target.blocked_until = None
        info = "Użytkownik został odblokowany."
    else:
        info = "Użytkownik został zablokowany."
    target.save(update_fields=["is_blocked", "blocked_until"])
    messages.success(request, info)
    return redirect(redirect_url)


@login_required
def report_user(request, pk):
    target = get_object_or_404(User.objects.select_related("active_voice_channel"), pk=pk)
    if target == request.user:
        messages.error(request, "Nie możesz zgłosić własnego konta.")
        return redirect("users:directory")

    form = UserReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.reporter = request.user
        report.target_user = target
        report.save()
        notify_moderators_about_report(report)
        messages.success(
            request,
            f"Zgłoszenie dotyczące użytkownika {target.username} zostało zapisane.",
        )
        return redirect("users:reports")

    return render(
        request,
        "users/report_form.html",
        {
            "form": form,
            "target_user": target,
        },
    )


@login_required
def reports(request):
    status_filter = request.GET.get("status", "").strip()
    valid_statuses = {choice[0] for choice in UserReport.STATUS_CHOICES}

    reports_qs = UserReport.objects.select_related(
        "reporter", "target_user", "reviewed_by", "target_user__active_voice_channel"
    )
    if request.user.can_moderate:
        is_moderation_view = True
    else:
        is_moderation_view = False
        reports_qs = reports_qs.filter(reporter=request.user)

    if status_filter in valid_statuses:
        reports_qs = reports_qs.filter(status=status_filter)
    else:
        status_filter = ""

    report_rows = [
        {
            "report": report,
            "review_form": UserReportReviewForm(instance=report),
        }
        for report in reports_qs
    ]

    return render(
        request,
        "users/report_list.html",
        {
            "report_rows": report_rows,
            "status_filter": status_filter,
            "status_choices": UserReport.STATUS_CHOICES,
            "is_moderation_view": is_moderation_view,
        },
    )


@login_required
@require_POST
def review_report(request, pk):
    if not request.user.can_moderate:
        raise PermissionDenied("Brak uprawnień do obsługi zgłoszeń.")

    report = get_object_or_404(
        UserReport.objects.select_related("reporter", "target_user"),
        pk=pk,
    )
    form = UserReportReviewForm(request.POST, instance=report)
    if not form.is_valid():
        messages.error(request, "Nie udało się zaktualizować zgłoszenia.")
        return redirect("users:reports")

    updated_report = form.save(commit=False)
    updated_report.reviewed_by = request.user
    updated_report.reviewed_at = timezone.now()
    updated_report.save()
    notify_reporter_about_report_update(updated_report, request.user)
    messages.success(
        request,
        f"Zgłoszenie dotyczące użytkownika {updated_report.target_user.username} zostało zaktualizowane.",
    )
    return redirect("users:reports")
