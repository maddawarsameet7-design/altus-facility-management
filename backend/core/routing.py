from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<request_id>[^/]+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/location/(?P<worker_id>[^/]+)/$', consumers.LocationConsumer.as_asgi()),
]
