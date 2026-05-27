from django.urls import path

from .views import (
    CustomLoginView,
    RegisterView,
    directory,
    profile_edit,
    report_user,
    reports,
    review_report,
    toggle_block,
    update_role,
)

app_name = "users"

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("register/", RegisterView.as_view(), name="register"),
    path("profile/", profile_edit, name="profile"),
    path("directory/", directory, name="directory"),
    path("directory/<int:pk>/role/", update_role, name="update_role"),
    path("directory/<int:pk>/block/", toggle_block, name="toggle_block"),
    path("directory/<int:pk>/report/", report_user, name="report_user"),
    path("reports/", reports, name="reports"),
    path("reports/<int:pk>/review/", review_report, name="review_report"),
]
