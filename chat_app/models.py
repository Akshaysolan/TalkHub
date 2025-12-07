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
        
        
        
# Add this to your models.py file

class LoginActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_activities')
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('success', 'Success'), ('failed', 'Failed')])
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    device = models.CharField(max_length=50, null=True, blank=True)
    browser = models.CharField(max_length=50, null=True, blank=True)
    location = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'Login Activities'

    def __str__(self):
        return f"{self.user.username} - {self.status} - {self.timestamp}"





# chat_app/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os

# Your existing models (Room, Message, DirectMessage, ChatSession, ChatMessage, Profile) here...

class Email(models.Model):
    """Model for storing emails"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('inbox', 'Inbox'),
        ('important', 'Important'),
        ('trash', 'Trash'),
        ('spam', 'Spam'),
    ]
    
    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sent_emails',
        verbose_name='Sender'
    )
    recipients = models.ManyToManyField(
        User, 
        related_name='received_emails',
        verbose_name='Recipients'
    )
    cc_recipients = models.ManyToManyField(
        User, 
        related_name='cc_emails',
        blank=True,
        verbose_name='CC Recipients'
    )
    bcc_recipients = models.ManyToManyField(
        User, 
        related_name='bcc_emails',
        blank=True,
        verbose_name='BCC Recipients'
    )
    subject = models.CharField(
        max_length=255,
        verbose_name='Subject'
    )
    body = models.TextField(
        verbose_name='Message Body'
    )
    body_html = models.TextField(
        blank=True,
        null=True,
        verbose_name='HTML Body'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='sent',
        verbose_name='Status'
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name='Is Read'
    )
    is_starred = models.BooleanField(
        default=False,
        verbose_name='Is Starred/Important'
    )
    is_replied = models.BooleanField(
        default=False,
        verbose_name='Is Replied'
    )
    is_forwarded = models.BooleanField(
        default=False,
        verbose_name='Is Forwarded'
    )
    thread_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Thread ID'
    )
    parent_email = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name='Parent Email'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Created At'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At'
    )
    scheduled_send = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Scheduled Send Time'
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Read At'
    )
    labels = models.ManyToManyField(
        'EmailLabel',
        blank=True,
        related_name='emails',
        verbose_name='Labels'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email'
        verbose_name_plural = 'Emails'
        indexes = [
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['is_read', 'created_at']),
            models.Index(fields=['is_starred', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.sender.username} → {self.subject}"
    
    def mark_as_read(self):
        """Mark email as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_unread(self):
        """Mark email as unread"""
        self.is_read = False
        self.read_at = None
        self.save(update_fields=['is_read', 'read_at'])
    
    def toggle_star(self):
        """Toggle star/important status"""
        self.is_starred = not self.is_starred
        self.save(update_fields=['is_starred'])
    
    def move_to_trash(self):
        """Move email to trash"""
        self.status = 'trash'
        self.save(update_fields=['status'])
    
    def restore_from_trash(self):
        """Restore email from trash to inbox"""
        self.status = 'inbox'
        self.save(update_fields=['status'])
    
    def move_to_spam(self):
        """Move email to spam"""
        self.status = 'spam'
        self.save(update_fields=['status'])
    
    def get_recipients_list(self):
        """Get comma-separated list of recipient emails"""
        return ', '.join([user.email for user in self.recipients.all()])
    
    def get_cc_list(self):
        """Get comma-separated list of CC emails"""
        return ', '.join([user.email for user in self.cc_recipients.all()])
    
    def get_bcc_list(self):
        """Get comma-separated list of BCC emails"""
        return ', '.join([user.email for user in self.bcc_recipients.all()])
    
    def get_preview(self, length=100):
        """Get preview text of email body"""
        preview = self.body[:length]
        if len(self.body) > length:
            preview += '...'
        return preview
    
    @property
    def has_attachments(self):
        """Check if email has attachments"""
        return self.attachments.exists()


class EmailAttachment(models.Model):
    """Model for email attachments"""
    email = models.ForeignKey(
        Email,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='Email'
    )
    file = models.FileField(
        upload_to='email_attachments/%Y/%m/%d/',
        verbose_name='Attachment File'
    )
    file_name = models.CharField(
        max_length=255,
        verbose_name='File Name'
    )
    file_size = models.BigIntegerField(
        verbose_name='File Size (bytes)'
    )
    file_type = models.CharField(
        max_length=100,
        verbose_name='File Type'
    )
    uploaded_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Uploaded At'
    )
    is_inline = models.BooleanField(
        default=False,
        verbose_name='Is Inline Attachment'
    )
    content_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Content ID (for inline)'
    )
    
    class Meta:
        ordering = ['uploaded_at']
        verbose_name = 'Email Attachment'
        verbose_name_plural = 'Email Attachments'
        indexes = [
            models.Index(fields=['email', 'uploaded_at']),
        ]
    
    def __str__(self):
        return self.file_name
    
    def save(self, *args, **kwargs):
        # Set file name and size if not set
        if not self.file_name and self.file:
            self.file_name = os.path.basename(self.file.name)
        
        if not self.file_size and self.file:
            try:
                self.file_size = self.file.size
            except:
                self.file_size = 0
        
        # Determine file type from extension
        if not self.file_type and self.file_name:
            ext = os.path.splitext(self.file_name)[1].lower()
            self.file_type = ext
        
        super().save(*args, **kwargs)
    
    @property
    def file_size_display(self):
        """Get human-readable file size"""
        if self.file_size < 1024:
            return f"{self.file_size} bytes"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
    
    @property
    def download_url(self):
        """Get download URL for attachment"""
        return self.file.url if self.file else None


class EmailLabel(models.Model):
    """Model for email labels/folders"""
    COLOR_CHOICES = [
        ('primary', 'Blue'),
        ('secondary', 'Gray'),
        ('success', 'Green'),
        ('danger', 'Red'),
        ('warning', 'Yellow'),
        ('info', 'Cyan'),
        ('light', 'Light'),
        ('dark', 'Dark'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_labels',
        verbose_name='User'
    )
    name = models.CharField(
        max_length=50,
        verbose_name='Label Name'
    )
    color = models.CharField(
        max_length=20,
        choices=COLOR_CHOICES,
        default='primary',
        verbose_name='Label Color'
    )
    is_system = models.BooleanField(
        default=False,
        verbose_name='Is System Label'
    )
    system_type = models.CharField(
        max_length=20,
        choices=[
            ('inbox', 'Inbox'),
            ('sent', 'Sent'),
            ('drafts', 'Drafts'),
            ('important', 'Important'),
            ('trash', 'Trash'),
            ('spam', 'Spam'),
            ('starred', 'Starred'),
        ],
        blank=True,
        null=True,
        verbose_name='System Label Type'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Created At'
    )
    
    class Meta:
        ordering = ['-is_system', 'name']
        verbose_name = 'Email Label'
        verbose_name_plural = 'Email Labels'
        unique_together = ['user', 'name']
        indexes = [
            models.Index(fields=['user', 'is_system']),
        ]
    
    def __str__(self):
        return f"{self.user.username}: {self.name}"
    
    @classmethod
    def create_system_labels(cls, user):
        """Create system labels for a user"""
        system_labels = [
            {'name': 'Inbox', 'system_type': 'inbox', 'color': 'primary'},
            {'name': 'Sent', 'system_type': 'sent', 'color': 'success'},
            {'name': 'Drafts', 'system_type': 'drafts', 'color': 'secondary'},
            {'name': 'Important', 'system_type': 'important', 'color': 'warning'},
            {'name': 'Trash', 'system_type': 'trash', 'color': 'danger'},
            {'name': 'Spam', 'system_type': 'spam', 'color': 'dark'},
            {'name': 'Starred', 'system_type': 'starred', 'color': 'info'},
        ]
        
        for label_data in system_labels:
            cls.objects.get_or_create(
                user=user,
                name=label_data['name'],
                defaults={
                    'color': label_data['color'],
                    'is_system': True,
                    'system_type': label_data['system_type']
                }
            )


class EmailContact(models.Model):
    """Model for storing email contacts"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_contacts',
        verbose_name='User'
    )
    contact_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='as_email_contact',
        verbose_name='Contact User',
        null=True,
        blank=True
    )
    email = models.EmailField(
        verbose_name='Email Address'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Contact Name'
    )
    company = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Company'
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Phone Number'
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notes'
    )
    is_favorite = models.BooleanField(
        default=False,
        verbose_name='Is Favorite'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Created At'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At'
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Email Contact'
        verbose_name_plural = 'Email Contacts'
        unique_together = ['user', 'email']
        indexes = [
            models.Index(fields=['user', 'is_favorite']),
            models.Index(fields=['user', 'email']),
        ]
    
    def __str__(self):
        return f"{self.name} <{self.email}>"
    
    def get_display_name(self):
        """Get display name for the contact"""
        if self.contact_user:
            return self.contact_user.get_full_name() or self.contact_user.username
        return self.name


class EmailSignature(models.Model):
    """Model for email signatures"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_signatures',
        verbose_name='User'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Signature Name'
    )
    content = models.TextField(
        verbose_name='Signature Content'
    )
    content_html = models.TextField(
        blank=True,
        null=True,
        verbose_name='HTML Content'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='Is Default Signature'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Created At'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Updated At'
    )
    
    class Meta:
        ordering = ['-is_default', 'name']
        verbose_name = 'Email Signature'
        verbose_name_plural = 'Email Signatures'
        indexes = [
            models.Index(fields=['user', 'is_default']),
        ]
    
    def __str__(self):
        return f"{self.user.username}: {self.name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default signature per user
        if self.is_default:
            EmailSignature.objects.filter(
                user=self.user, 
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class EmailFilter(models.Model):
    """Model for email filters/rules"""
    ACTION_CHOICES = [
        ('move', 'Move to folder'),
        ('label', 'Apply label'),
        ('mark_read', 'Mark as read'),
        ('delete', 'Delete'),
        ('forward', 'Forward to'),
        ('reply', 'Auto-reply'),
    ]
    
    CONDITION_CHOICES = [
        ('contains', 'Contains'),
        ('not_contains', 'Does not contain'),
        ('equals', 'Equals'),
        ('not_equals', 'Does not equal'),
        ('starts_with', 'Starts with'),
        ('ends_with', 'Ends with'),
    ]
    
    FIELD_CHOICES = [
        ('sender', 'Sender'),
        ('recipient', 'Recipient'),
        ('subject', 'Subject'),
        ('body', 'Body'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_filters',
        verbose_name='User'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='Filter Name'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Is Active'
    )
    field = models.CharField(
        max_length=20,
        choices=FIELD_CHOICES,
        verbose_name='Field to Check'
    )
    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        verbose_name='Condition'
    )
    value = models.CharField(
        max_length=255,
        verbose_name='Value to Match'
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name='Action'
    )
    action_value = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Action Value'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Created At'
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Email Filter'
        verbose_name_plural = 'Email Filters'
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.username}: {self.name}"
    
    def apply_to_email(self, email):
        """Apply filter to email if conditions match"""
        # Get field value from email
        if self.field == 'sender':
            field_value = email.sender.email
        elif self.field == 'recipient':
            field_value = email.get_recipients_list()
        elif self.field == 'subject':
            field_value = email.subject
        elif self.field == 'body':
            field_value = email.body
        else:
            return False
        
        # Check condition
        matches = False
        if self.condition == 'contains':
            matches = self.value.lower() in field_value.lower()
        elif self.condition == 'not_contains':
            matches = self.value.lower() not in field_value.lower()
        elif self.condition == 'equals':
            matches = field_value.lower() == self.value.lower()
        elif self.condition == 'not_equals':
            matches = field_value.lower() != self.value.lower()
        elif self.condition == 'starts_with':
            matches = field_value.lower().startswith(self.value.lower())
        elif self.condition == 'ends_with':
            matches = field_value.lower().endswith(self.value.lower())
        
        if matches:
            self.execute_action(email)
            return True
        return False
    
    def execute_action(self, email):
        """Execute the filter action on the email"""
        if self.action == 'move':
            # Move to folder/label
            pass
        elif self.action == 'label':
            # Apply label
            pass
        elif self.action == 'mark_read':
            email.mark_as_read()
        elif self.action == 'delete':
            email.move_to_trash()
        elif self.action == 'forward':
            # Forward logic
            pass
        elif self.action == 'reply':
            # Auto-reply logic
            pass


class EmailNotification(models.Model):
    """Model for email notifications"""
    NOTIFICATION_TYPES = [
        ('new_email', 'New Email'),
        ('email_read', 'Email Read'),
        ('email_replied', 'Email Replied'),
        ('email_forwarded', 'Email Forwarded'),
        ('email_deleted', 'Email Deleted'),
        ('email_starred', 'Email Starred'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_notifications',
        verbose_name='User'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        verbose_name='Notification Type'
    )
    email = models.ForeignKey(
        Email,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Email',
        null=True,
        blank=True
    )
    message = models.CharField(
        max_length=255,
        verbose_name='Notification Message'
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name='Is Read'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Created At'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email Notification'
        verbose_name_plural = 'Email Notifications'
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username}: {self.notification_type}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.save(update_fields=['is_read'])