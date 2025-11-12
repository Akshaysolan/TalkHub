import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Room, Message

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        
        logger.info(f"WebSocket connection attempt for room: {self.room_name}")
        logger.info(f"User: {self.scope.get('user', 'Anonymous')}")

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"WebSocket connection accepted for room: {self.room_name}")

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected for room: {self.room_name}, code: {close_code}")
        
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json['message']
            username = text_data_json['username']
            room_name = text_data_json['room_name']

            logger.info(f"Message received in room {room_name} from {username}")

            # Save message to database
            await self.save_message(room_name, username, message)

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'username': username
                }
            )
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self.send(text_data=json.dumps({
                'error': str(e)
            }))

    async def chat_message(self, event):
        message = event['message']
        username = event['username']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'username': username
        }))

    @database_sync_to_async
    def save_message(self, room_name, username, content):
        try:
            room = Room.objects.get(name=room_name)
            user = User.objects.get(username=username)
            Message.objects.create(room=room, user=user, content=content)
        except Room.DoesNotExist:
            room = Room.objects.create(name=room_name)
            user = User.objects.get(username=username)
            Message.objects.create(room=room, user=user, content=content)
        except Exception as e:
            logger.error(f"Error saving message: {e}")