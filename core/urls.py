from django.urls import path

from .views import (
    custom_404,
    home,
    notification_open,
    notifications,
    notifications_feed,
    search,
    ui_state,
)

app_name = "core"

urlpatterns = [
    path("", home, name="home"),
    path("search/", search, name="search"),
    path("ui-state/", ui_state, name="ui_state"),
    path("notifications/", notifications, name="notifications"),
    path("notifications/feed/", notifications_feed, name="notifications_feed"),
    path("notifications/<int:pk>/open/", notification_open, name="notification_open"),
]
