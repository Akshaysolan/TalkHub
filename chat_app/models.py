# chat_app/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    @property
    def created_at(self):
        """Return the user's creation date as a fallback"""
        return self.user.date_joined

class Room(models.Model):
    ROOM_TYPES = (
        ('direct', 'Direct Message'),
        ('group', 'Group Chat'),
    )
    
    PRIVACY_CHOICES = (
        ('public', 'Public'),
        ('private', 'Private'),
    )
    
    CATEGORY_CHOICES = (
        ('general', 'General'),
        ('work', 'Work'),
        ('friends', 'Friends'),
        ('family', 'Family'),
        ('project', 'Project'),
        ('hobby', 'Hobby'),
        ('education', 'Education'),
        ('other', 'Other'),
    )
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    room_type = models.CharField(max_length=10, choices=ROOM_TYPES, default='group')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    privacy = models.CharField(max_length=10, choices=PRIVACY_CHOICES, default='public')
    allow_invites = models.BooleanField(default=True)
    moderate_content = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
    members = models.ManyToManyField(User, related_name='chat_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"
    
    class Meta:
        ordering = ['-updated_at']

class Message(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    is_system_message = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f'{self.user.username}: {self.content[:20]}'

class DirectMessage(models.Model):
    sender = models.ForeignKey(User, related_name='sent_direct_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_direct_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['sender', 'receiver', 'timestamp']),
        ]

    def __str__(self):
        return f'DM {self.sender.username} -> {self.receiver.username}: {self.content[:20]}'

class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or f"Chat {self.id}"

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=20)  # 'user' or 'ai'
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender}: {self.content[:30]}"

class GroupInvitation(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    invited_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_invitations')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Invitation to {self.room.name} for {self.invited_user.username}"

# Signal to create profile when user is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a Profile instance when a new User is created"""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the profile when the User is saved"""
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        # If for some reason profile doesn't exist, create it
        Profile.objects.create(user=instance)