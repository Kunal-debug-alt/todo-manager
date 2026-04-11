from django.urls import path

from tasks.consumers import RealtimeConsumer

websocket_urlpatterns = [
    path('ws/user/', RealtimeConsumer.as_asgi()),
    path('ws/project/<int:project_id>/', RealtimeConsumer.as_asgi()),
]
