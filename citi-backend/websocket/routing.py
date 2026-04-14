from django.urls import re_path
from .consumers import RailUpdateConsumer

websocket_urlpatterns = [
    re_path(r'ws/rail-updates/$', RailUpdateConsumer.as_asgi()),
]
