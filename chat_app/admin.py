from django.contrib import admin
from .models import (
    Email, EmailAttachment, EmailLabel, 
    EmailContact, EmailSignature, EmailFilter,
    EmailNotification
)

from .models import Room, Message

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['user', 'room', 'content', 'timestamp']
    list_filter = ['room', 'timestamp']
    search_fields = ['content', 'user__username']



@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'status', 'is_read', 'is_starred', 'created_at')
    list_filter = ('status', 'is_read', 'is_starred', 'created_at')
    search_fields = ('subject', 'body', 'sender__username')
    filter_horizontal = ('recipients', 'cc_recipients', 'bcc_recipients', 'labels')
    readonly_fields = ('created_at', 'updated_at', 'read_at')
    fieldsets = (
        ('Email Information', {
            'fields': ('sender', 'recipients', 'cc_recipients', 'bcc_recipients', 'subject')
        }),
        ('Content', {
            'fields': ('body', 'body_html')
        }),
        ('Status', {
            'fields': ('status', 'is_read', 'is_starred', 'is_replied', 'is_forwarded')
        }),
        ('Metadata', {
            'fields': ('thread_id', 'parent_email', 'scheduled_send', 'read_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'email', 'file_size_display', 'file_type', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at')
    search_fields = ('file_name', 'email__subject')
    readonly_fields = ('uploaded_at', 'file_size', 'file_type')

@admin.register(EmailLabel)
class EmailLabelAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'color', 'is_system', 'system_type', 'created_at')
    list_filter = ('is_system', 'color', 'system_type')
    search_fields = ('name', 'user__username')
    readonly_fields = ('created_at',)

@admin.register(EmailContact)
class EmailContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'user', 'company', 'is_favorite', 'created_at')
    list_filter = ('is_favorite', 'created_at')
    search_fields = ('name', 'email', 'company', 'user__username')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(EmailSignature)
class EmailSignatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_default', 'created_at')
    list_filter = ('is_default', 'created_at')
    search_fields = ('name', 'user__username', 'content')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(EmailFilter)
class EmailFilterAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_active', 'field', 'condition', 'action', 'created_at')
    list_filter = ('is_active', 'field', 'condition', 'action')
    search_fields = ('name', 'user__username', 'value')
    readonly_fields = ('created_at',)

@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('message', 'user__username')
    readonly_fields = ('created_at',)