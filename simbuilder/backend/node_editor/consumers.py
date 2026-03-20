"""WebSocket consumers for real-time graph updates."""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import GraphProject, NodeInstance
import logging

logger = logging.getLogger(__name__)


class GraphEditorConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time collaborative editing."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.project_id = self.scope['url_route']['kwargs']['project_id']
        self.room_group_name = f'graph_{self.project_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"WebSocket connected to project {self.project_id}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected from project {self.project_id}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages.

        Message format:
        {
            "type": "node_update" | "node_create" | "node_delete" |
                    "connection_create" | "connection_delete",
            "data": {...}
        }
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            # Broadcast to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'graph_message',
                    'message_type': message_type,
                    'data': data.get('data'),
                    'sender': self.channel_name
                }
            )
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON format'
            }))

    async def graph_message(self, event):
        """Send message to WebSocket client.

        Args:
            event: Message event from channel layer
        """
        # Don't send message back to sender
        if event.get('sender') == self.channel_name:
            return

        await self.send(text_data=json.dumps({
            'type': event['message_type'],
            'data': event['data']
        }))
