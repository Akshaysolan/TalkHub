# Create a management command to setup email system
# chat_app/management/commands/setup_email.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from chat_app.models import EmailLabel

class Command(BaseCommand):
    help = 'Setup email system with initial data'
    
    def handle(self, *args, **kwargs):
        # Create system email labels for all users
        users = User.objects.all()
        for user in users:
            EmailLabel.create_system_labels(user)
        
        self.stdout.write(
            self.style.SUCCESS(f'Created email labels for {users.count()} users')
        )