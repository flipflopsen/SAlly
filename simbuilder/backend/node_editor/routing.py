"""WebSocket routing configuration."""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # WebSocket endpoint for real-time graph editing
    # URL: ws://localhost:8000/ws/graph/{project_id}/
    re_path(
        r'ws/graph/(?P<project_id>\d+)/$',
        consumers.GraphEditorConsumer.as_asgi()
    ),
]

# This generates:
# WS  /ws/graph/1/  - WebSocket connection for project 1
# WS  /ws/graph/2/  - WebSocket connection for project 2
# etc.
