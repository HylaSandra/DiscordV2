from django.urls import path

from .views import custom_404, home, notification_open, notifications, search

app_name = "core"

urlpatterns = [
    path("", home, name="home"),
    path("search/", search, name="search"),
    path("notifications/", notifications, name="notifications"),
    path("notifications/<int:pk>/open/", notification_open, name="notification_open"),
]

