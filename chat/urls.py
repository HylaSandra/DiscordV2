from django.urls import path

from .views import (
    add_channel_member,
    ban_channel_member,
    channel_detail,
    create_channel,
    dashboard,
    delete_message,
    edit_message,
    join_channel,
    manage_channel,
    manage_channels,
    mark_channel_read,
    mark_thread_read,
    post_channel_message,
    post_thread_message,
    remove_channel_member,
    start_thread,
    thread_detail,
    toggle_channel_moderator,
    toggle_reaction,
    unban_channel_member,
    voice_room,
)

app_name = "chat"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("channels/manage/", manage_channels, name="manage_channels"),
    path("channels/<slug:slug>/manage/", manage_channel, name="manage_channel"),
    path("channels/create/", create_channel, name="create_channel"),
    path("channels/<slug:slug>/join/", join_channel, name="join_channel"),
    path("channels/<slug:slug>/members/add/", add_channel_member, name="add_channel_member"),
    path(
        "channels/<slug:slug>/members/<int:user_id>/remove/",
        remove_channel_member,
        name="remove_channel_member",
    ),
    path(
        "channels/<slug:slug>/members/<int:user_id>/ban/",
        ban_channel_member,
        name="ban_channel_member",
    ),
    path(
        "channels/<slug:slug>/bans/<int:user_id>/remove/",
        unban_channel_member,
        name="unban_channel_member",
    ),
    path(
        "channels/<slug:slug>/moderators/<int:user_id>/toggle/",
        toggle_channel_moderator,
        name="toggle_channel_moderator",
    ),
    path("channels/<slug:slug>/", channel_detail, name="channel_detail"),
    path("channels/<slug:slug>/post/", post_channel_message, name="post_channel_message"),
    path("channels/<slug:slug>/read/", mark_channel_read, name="mark_channel_read"),
    path("dm/start/<str:username>/", start_thread, name="start_thread"),
    path("dm/<int:pk>/", thread_detail, name="thread_detail"),
    path("dm/<int:pk>/post/", post_thread_message, name="post_thread_message"),
    path("dm/<int:pk>/read/", mark_thread_read, name="mark_thread_read"),
    path("voice/<slug:slug>/", voice_room, name="voice_room"),
    path("messages/<int:pk>/edit/", edit_message, name="edit_message"),
    path("messages/<int:pk>/delete/", delete_message, name="delete_message"),
    path("messages/<int:pk>/react/", toggle_reaction, name="toggle_reaction"),
]
