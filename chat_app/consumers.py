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
            room_name = text_data_json.get('room_name', self.room_name)

            logger.info(f"Message received in room {room_name} from {username}")

            # Save message to database
            await self.save_message(room_name, username, message)

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'username': username,
                    'room_name': room_name
                }
            )
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self.send(text_data=json.dumps({
                'error': str(e),
                'type': 'error'
            }))

    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        room_name = event.get('room_name', self.room_name)

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'username': username,
            'room_name': room_name,
            'type': 'chat_message'
        }))

    @database_sync_to_async
    def save_message(self, room_name, username, content):
        try:
            room = Room.objects.get(name=room_name)
            user = User.objects.get(username=username)
            Message.objects.create(room=room, user=user, content=content)
            logger.info(f"Message saved to database for room: {room_name}")
        except Room.DoesNotExist:
            # Create room if it doesn't exist (for backward compatibility)
            try:
                room = Room.objects.create(
                    name=room_name,
                    room_type='group',
                    created_by=user
                )
                room.members.add(user)
                Message.objects.create(room=room, user=user, content=content)
                logger.info(f"New room created and message saved: {room_name}")
            except Exception as e:
                logger.error(f"Error creating room: {e}")
                raise
        except User.DoesNotExist:
            logger.error(f"User {username} does not exist")
            raise
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            raise

    # Additional methods for enhanced functionality
    async def user_joined(self, event):
        """Handle user join notifications"""
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'username': event['username'],
            'message': f"{event['username']} joined the chat",
            'timestamp': event.get('timestamp')
        }))

    async def user_left(self, event):
        """Handle user leave notifications"""
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'username': event['username'],
            'message': f"{event['username']} left the chat",
            'timestamp': event.get('timestamp')
        }))

    async def typing_started(self, event):
        """Handle typing indicators"""
        await self.send(text_data=json.dumps({
            'type': 'typing_started',
            'username': event['username']
        }))

    async def typing_stopped(self, event):
        """Handle typing stop indicators"""
        await self.send(text_data=json.dumps({
            'type': 'typing_stopped',
            'username': event['username']
        }))
        
        

class VideoCallConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.me = self.scope["user"].username
        self.other = self.scope["url_route"]["kwargs"]["username"]

        self.room = f"video_{self.me}_{self.other}"
        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        await self.channel_layer.group_send(
            self.room,
            {
                "type": "signal_message",
                "data": data
            }
        )

    async def signal_message(self, event):
        await self.send(text_data=json.dumps(event["data"]))
