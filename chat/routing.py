from django.urls import re_path

from .consumers import ChannelConsumer, DirectMessageConsumer, VoiceSignalingConsumer

websocket_urlpatterns = [
    re_path(r"ws/channel/(?P<slug>[-\w]+)/$", ChannelConsumer.as_asgi()),
    re_path(r"ws/dm/(?P<thread_id>\d+)/$", DirectMessageConsumer.as_asgi()),
    re_path(r"ws/voice/(?P<slug>[-\w]+)/$", VoiceSignalingConsumer.as_asgi()),
]

