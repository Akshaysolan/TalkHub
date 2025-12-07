from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from .models import Room, Message, DirectMessage, ChatSession, ChatMessage, Profile
from django.contrib.auth.models import User
from django.db.models import Q, Max, Count
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import json
import os
from groq import Groq
from django.views.decorators.csrf import csrf_exempt

# Import the new email models with try-except
try:
    from .models import Email, EmailAttachment, EmailContact, LoginActivity
    EMAIL_MODELS_EXIST = True
except ImportError:
    EMAIL_MODELS_EXIST = False

# ============ AUTHENTICATION VIEWS ============

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('chat_app:index')
    else:
        form = UserCreationForm()
    return render(request, 'chat_app/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('chat_app:index')
    else:
        form = AuthenticationForm()
    return render(request, 'chat_app/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('chat_app:login')

# ============ CHAT VIEWS ============

@login_required
def index(request):
    # Get all rooms
    rooms = Room.objects.all().order_by('-created_at')
    
    # Count messages for each room
    for room in rooms:
        room.message_count = room.messages.count()
    
    # Get basic stats
    total_rooms_count = rooms.count()
    today_messages_count = Message.objects.filter(
        timestamp__date=timezone.now().date()
    ).count()
    
    context = {
        'rooms': rooms,
        'favorite_rooms': [],  # Empty for now
        'online_users_count': 1,  # Just the current user
        'today_messages_count': today_messages_count,
        'total_rooms_count': total_rooms_count,
    }
    return render(request, 'chat_app/index.html', context)

@login_required
def room(request, room_name):
    room_obj = get_object_or_404(Room, name=room_name)
    messages = Message.objects.filter(room=room_obj).select_related('user')[:50]
    
    return render(request, 'chat_app/room.html', {
        'room': room_obj,
        'messages': messages,
        'room_users': [],  # Empty for now
        'is_favorited': False,  # False for now
    })

@login_required
def create_room(request):
    if request.method == 'POST':
        room_name = request.POST.get('room_name')
        if room_name:
            room_obj, created = Room.objects.get_or_create(
                name=room_name,
                defaults={'created_by': request.user}
            )
            return redirect('chat_app:room', room_name=room_obj.name)
    return redirect('chat_app:index')

# ============ DIRECT MESSAGE VIEWS ============

@login_required
def direct_messages(request):
    """List user's DM conversations"""
    # Get header stats
    total_rooms_count = Room.objects.count()
    today_messages_count = Message.objects.filter(
        timestamp__date=timezone.now().date()
    ).count()
    
    # fetch all DMs involving current user
    dms = DirectMessage.objects.filter(Q(sender=request.user) | Q(receiver=request.user))
    
    # find conversation partners
    partners = set()
    for dm in dms:
        if dm.sender == request.user:
            partners.add(dm.receiver)
        else:
            partners.add(dm.sender)
    
    # Build conversation summaries
    conversations = []
    for other in partners:
        # last message between the two
        last_msg = DirectMessage.objects.filter(
            Q(sender=request.user, receiver=other) | Q(sender=other, receiver=request.user)
        ).order_by('-timestamp').first()
        unread_count = DirectMessage.objects.filter(sender=other, receiver=request.user, is_read=False).count()
        conversations.append({
            'user': other,
            'last_message': last_msg,
            'unread_count': unread_count,
        })
    
    # sort conversations by last_message timestamp desc
    conversations.sort(key=lambda c: c['last_message'].timestamp if c['last_message'] else timezone.datetime.min, reverse=True)

    context = {
        'dm_conversations': conversations,
        # Add header stats
        'total_rooms_count': total_rooms_count,
        'today_messages_count': today_messages_count,
        'online_users_count': 1,  # Just the current user
    }
    return render(request, 'chat_app/direct_messages.html', context)

@login_required
def direct_message_chat(request, username):
    """Render chat view between request.user and username"""
    other_user = get_object_or_404(User, username=username)
    if other_user == request.user:
        return redirect('chat_app:direct_messages')

    # fetch messages between the two
    messages = DirectMessage.objects.filter(
        (Q(sender=request.user) & Q(receiver=other_user)) |
        (Q(sender=other_user) & Q(receiver=request.user))
    ).select_related('sender', 'receiver').order_by('timestamp')

    # mark messages sent to request.user as read
    DirectMessage.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)

    return render(request, 'chat_app/direct_message_chat.html', {
        'other_user': other_user,
        'messages': messages,
    })

@login_required
def send_direct_message(request, username):
    """Send a DM to username"""
    if request.method != 'POST':
        return HttpResponseBadRequest('Only POST allowed.')

    other_user = get_object_or_404(User, username=username)
    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'status': 'error', 'message': 'Empty message.'})

    dm = DirectMessage.objects.create(sender=request.user, receiver=other_user, content=content)

    # Build response data
    message_data = {
        'id': dm.id,
        'sender': dm.sender.username,
        'receiver': dm.receiver.username,
        'content': dm.content,
        'timestamp': dm.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
    }
    return JsonResponse({'status': 'success', 'message': message_data})

@login_required
def get_direct_messages(request, username):
    """Return last N messages between request.user and username as JSON"""
    other = get_object_or_404(User, username=username)
    msgs = DirectMessage.objects.filter(
        (Q(sender=request.user) & Q(receiver=other)) |
        (Q(sender=other) & Q(receiver=request.user))
    ).select_related('sender', 'receiver').order_by('timestamp')[:200]

    data = []
    for m in msgs:
        data.append({
            'id': m.id,
            'sender': m.sender.username,
            'receiver': m.receiver.username,
            'content': m.content,
            'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        })
    return JsonResponse(data, safe=False)

# ============ GROUP CHAT VIEWS ============

@login_required
def group_chats(request):
    """Display user's group chats"""
    # Get header stats
    total_rooms_count = Room.objects.count()
    today_messages_count = Message.objects.filter(
        timestamp__date=timezone.now().date()
    ).count()
    
    # Get rooms where user is a member
    user_rooms = Room.objects.filter(
        members=request.user,
        room_type='group'
    ).distinct().prefetch_related('members', 'messages')
    
    # Add user_count and message_count to each room
    for room in user_rooms:
        room.user_count = room.members.count()
        room.message_count = room.messages.count()
    
    context = {
        'user_rooms': user_rooms,
        # Add header stats
        'total_rooms_count': total_rooms_count,
        'today_messages_count': today_messages_count,
        'online_users_count': 1,  # Just the current user
    }
    return render(request, 'chat_app/group_chats.html', context)

@login_required
def create_group(request):
    """Create a new group chat"""
    if request.method == 'POST':
        group_name = request.POST.get('group_name', '').strip()
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', 'general')
        privacy = request.POST.get('privacy', 'public')
        allow_invites = request.POST.get('allow_invites') == 'on'
        moderate_content = request.POST.get('moderate_content') == 'on'
        
        # Validate group name
        if not group_name:
            messages.error(request, 'Group name is required.')
            return redirect('chat_app:group_chats')
        
        if len(group_name) < 3:
            messages.error(request, 'Group name must be at least 3 characters long.')
            return redirect('chat_app:group_chats')
        
        if len(group_name) > 50:
            messages.error(request, 'Group name cannot exceed 50 characters.')
            return redirect('chat_app:group_chats')
        
        # Check if room name already exists
        if Room.objects.filter(name=group_name).exists():
            messages.error(request, 'A group with this name already exists. Please choose a different name.')
            return redirect('chat_app:group_chats')
        
        try:
            # Create the group room
            room = Room.objects.create(
                name=group_name,
                description=description,
                room_type='group',
                category=category,
                privacy=privacy,
                allow_invites=allow_invites,
                moderate_content=moderate_content,
                created_by=request.user
            )
            
            # Add creator as first member
            room.members.add(request.user)
            
            # Create welcome message
            Message.objects.create(
                room=room,
                user=request.user,
                content=f"Welcome to {group_name}! This group was created by {request.user.username}."
            )
            
            messages.success(request, f'Group "{group_name}" created successfully!')
            return redirect('chat_app:room', room_name=room.name)
            
        except Exception as e:
            messages.error(request, f'Error creating group: {str(e)}')
            return redirect('chat_app:group_chats')
    
    return redirect('chat_app:group_chats')

@login_required
def start_group_chat(request, room_name):
    """Start a group chat session"""
    room = get_object_or_404(Room, name=room_name, room_type='group')
    
    # Check if user is a member of the group
    if not room.members.filter(id=request.user.id).exists():
        messages.error(request, 'You are not a member of this group.')
        return redirect('chat_app:group_chats')
    
    # Get recent messages
    messages_list = Message.objects.filter(room=room).order_by('timestamp')[:50]
    
    context = {
        'room': room,
        'messages': messages_list,
        'room_name': room_name,
    }
    return render(request, 'chat_app/room.html', context)

# ============ SETTINGS VIEW ============

@login_required
def settings(request):
    """Settings view with profile management and password change"""
    try:
        # Get or create profile
        profile, created = Profile.objects.get_or_create(user=request.user)
    except Exception as e:
        # Fallback if Profile model has issues
        profile = {
            'bio': '',
            'is_online': True,
            'last_seen': timezone.now()
        }
    
    # Get header stats
    total_rooms_count = Room.objects.count()
    today_messages_count = Message.objects.filter(
        timestamp__date=timezone.now().date()
    ).count()
    
    # Get login activity (if model exists)
    try:
        login_activities = LoginActivity.objects.filter(user=request.user).order_by('-timestamp')[:10]
    except:
        login_activities = []
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'profile':
            # Handle profile update
            email = request.POST.get('email', '').strip()
            bio = request.POST.get('bio', '').strip()
            
            # Update email if changed and valid
            if email and email != request.user.email:
                try:
                    validate_email(email)
                    # Check if email already exists
                    if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'message': 'This email is already registered with another account.'
                            })
                        messages.error(request, 'This email is already registered with another account.')
                    else:
                        request.user.email = email
                        request.user.save()
                except ValidationError:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'message': 'Please enter a valid email address.'
                        })
                    messages.error(request, 'Please enter a valid email address.')
            
            # Update bio if profile exists
            if hasattr(profile, 'bio'):
                profile.bio = bio
                profile.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Profile updated successfully!',
                    'new_email': request.user.email
                })
            messages.success(request, 'Profile updated successfully!')
            
        elif form_type == 'password_change':
            # Handle password change
            current_password = request.POST.get('current_password', '')
            new_password1 = request.POST.get('new_password1', '')
            new_password2 = request.POST.get('new_password2', '')
            
            # Validate current password
            if not request.user.check_password(current_password):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'Current password is incorrect.'
                    })
                messages.error(request, 'Current password is incorrect.')
                return redirect('chat_app:settings')
            
            # Validate new passwords match
            if new_password1 != new_password2:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'New passwords do not match.'
                    })
                messages.error(request, 'New passwords do not match.')
                return redirect('chat_app:settings')
            
            # Validate password strength
            if len(new_password1) < 8:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'Password must be at least 8 characters long.'
                    })
                messages.error(request, 'Password must be at least 8 characters long.')
                return redirect('chat_app:settings')
            
            # Change password
            try:
                request.user.set_password(new_password1)
                request.user.save()
                
                # Update session to prevent logout
                update_session_auth_hash(request, request.user)
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': 'Password changed successfully!'
                    })
                messages.success(request, 'Password changed successfully!')
                return redirect('chat_app:settings')
                
            except Exception as e:
                error_message = f'Error changing password: {str(e)}'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': error_message
                    })
                messages.error(request, error_message)
                return redirect('chat_app:settings')
    
    # For GET requests
    context = {
        'profile': profile,
        'login_activities': login_activities,
        'total_rooms_count': total_rooms_count,
        'today_messages_count': today_messages_count,
        'online_users_count': 1,
    }
    return render(request, 'chat_app/settings.html', context)

# ============ AI ASSISTANT VIEWS ============

# Configure Groq client
GROQ_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

def ask_groq(message):
    """Call Groq chat completion and return assistant text"""
    if client is None:
        return "AI not configured (GROQ_API_KEY missing)."

    try:
        resp = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            messages=[{"role": "user", "content": message}]
        )

        # Use dot access
        choice = getattr(resp.choices[0], "message", None)
        if choice is None:
            # fallback: try the older style if available
            return str(resp)
        return choice.content

    except Exception as e:
        return f"Error: {str(e)}"

@login_required
def ai_assistant_view(request):
    """Main AI assistant page"""
    return render(request, 'chat_app/ai_assistant.html', {})

@login_required
def ai_chat_api(request):
    """Send message -> returns AI reply and stores both messages"""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    session_id = request.POST.get("session_id")
    message = request.POST.get("message", "").strip()
    if not message:
        return JsonResponse({"reply": "Message cannot be empty."})

    # get or create session if not provided
    if session_id:
        try:
            session = ChatSession.objects.get(id=int(session_id), user=request.user)
        except ChatSession.DoesNotExist:
            return JsonResponse({"error": "Session not found."}, status=404)
    else:
        session = ChatSession.objects.create(user=request.user, title=(message[:50] or "New chat"))

    # save user message
    ChatMessage.objects.create(session=session, sender='user', content=message)

    # ask AI
    ai_reply = ask_groq(message)

    # save AI message
    ChatMessage.objects.create(session=session, sender='ai', content=ai_reply)

    # update session title (first user message as title if empty)
    if not session.title:
        session.title = message[:60]
        session.save()

    return JsonResponse({
        "reply": ai_reply,
        "session_id": session.id,
    })

@login_required
def ai_sessions_list(request):
    """GET: return list of sessions, POST: create empty session"""
    if request.method == "GET":
        sessions = ChatSession.objects.filter(user=request.user).order_by('-updated_at')
        data = []
        for s in sessions:
            last_msg = s.messages.last()
            preview = (last_msg.content[:80] + '...') if last_msg else ''
            data.append({
                "id": s.id,
                "title": s.title or f"Chat {s.id}",
                "updated_at": s.updated_at.isoformat(),
                "preview": preview,
            })
        return JsonResponse(data, safe=False)

    if request.method == "POST":
        # create new empty session
        s = ChatSession.objects.create(user=request.user, title=request.POST.get("title", "New chat"))
        return JsonResponse({"id": s.id, "title": s.title})

@login_required
def ai_session_detail(request, session_id):
    """GET messages for session"""
    s = get_object_or_404(ChatSession, id=session_id, user=request.user)
    msgs = s.messages.all().values("id", "sender", "content", "timestamp")
    return JsonResponse(list(msgs), safe=False)

@login_required
def ai_delete_session(request, session_id):
    """Delete a specific AI session"""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)
    s = get_object_or_404(ChatSession, id=session_id, user=request.user)
    s.delete()
    return JsonResponse({"deleted": True})

@login_required
def ai_delete_all_sessions(request):
    """Delete all AI sessions for the user"""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)
    ChatSession.objects.filter(user=request.user).delete()
    return JsonResponse({"deleted_all": True})

# ============ UTILITY VIEWS ============

@login_required
def favorites(request):
    return render(request, 'chat_app/favorites.html', {
        'favorite_rooms': [],
    })

@login_required
def toggle_favorite(request, room_name):
    return JsonResponse({'status': 'error', 'is_favorited': False})

@login_required
def user_search(request):
    """GET ?q=... -> JSON list of users matching q (exclude request.user)"""
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse([], safe=False)
    users = User.objects.filter(username__icontains=q).exclude(pk=request.user.pk)[:10]
    results = []
    for u in users:
        profile = getattr(u, 'profile', None)
        is_online = getattr(profile, 'is_online', False) if profile else False
        results.append({
            'username': u.username,
            'is_online': bool(is_online),
        })
    return JsonResponse(results, safe=False)

@login_required
def get_messages(request, room_name):
    """Get messages for a room"""
    room_obj = get_object_or_404(Room, name=room_name)
    messages = Message.objects.filter(room=room_obj).select_related('user')[:50]
    messages_data = []
    for message in messages:
        messages_data.append({
            'username': message.user.username,
            'content': message.content,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    return JsonResponse(messages_data, safe=False)

# ============ EMAIL VIEWS (WITH DUMMY DATA) ============

@login_required
def email_api_check_new(request):
    """API endpoint for checking new emails - using real database"""
    # Get the timestamp from the request (if any)
    last_check = request.GET.get('last_check', None)
    
    if last_check:
        try:
            from django.utils.dateparse import parse_datetime
            last_check_dt = parse_datetime(last_check)
            
            # Count new emails since last check
            new_emails_count = Email.objects.filter(
                recipients=request.user,
                status='inbox',
                is_read=False,
                created_at__gt=last_check_dt
            ).count()
            
            has_new = new_emails_count > 0
            
            return JsonResponse({
                'has_new': has_new,
                'new_count': new_emails_count,
                'last_check': timezone.now().isoformat(),
                'message': f'{new_emails_count} new email(s)' if has_new else 'No new emails'
            })
        except:
            pass
    
    # Fallback: just check if there are any unread emails
    new_emails_count = Email.objects.filter(
        recipients=request.user,
        status='inbox',
        is_read=False
    ).count()
    
    return JsonResponse({
        'has_new': new_emails_count > 0,
        'new_count': new_emails_count,
        'last_check': timezone.now().isoformat(),
        'message': f'{new_emails_count} new email(s)' if new_emails_count > 0 else 'No new emails'
    })

@login_required
def emails(request):
    """Main email inbox view - render the email page with real stats"""
    # Add header stats for the email page
    total_rooms_count = Room.objects.count()
    today_messages_count = Message.objects.filter(
        timestamp__date=timezone.now().date()
    ).count()
    
    # Get email stats from database
    try:
        inbox_count = Email.objects.filter(
            recipients=request.user,
            status='inbox'
        ).count()
        
        unread_count = Email.objects.filter(
            recipients=request.user,
            status='inbox',
            is_read=False
        ).count()
        
        important_count = Email.objects.filter(
            recipients=request.user,
            status='inbox',
            is_starred=True
        ).count()
        
        sent_count = Email.objects.filter(
            sender=request.user,
            status='sent'
        ).count()
        
    except Exception as e:
        # If models don't exist yet, use dummy values
        inbox_count = 0
        unread_count = 0
        important_count = 0
        sent_count = 0
    
    context = {
        'total_rooms_count': total_rooms_count,
        'today_messages_count': today_messages_count,
        'online_users_count': 1,  # Just the current user
        'email_stats': {
            'inbox': inbox_count,
            'unread': unread_count,
            'important': important_count,
            'sent': sent_count,
        }
    }
    return render(request, 'chat_app/emails.html', context)

@login_required
def email_compose(request):
    """Compose email view"""
    # Add header stats
    total_rooms_count = Room.objects.count()
    today_messages_count = Message.objects.filter(
        timestamp__date=timezone.now().date()
    ).count()
    
    # Get user's contacts for auto-suggest
    try:
        from .models import EmailContact
        contacts = EmailContact.objects.filter(user=request.user)[:20]
        contact_list = [
            {'name': contact.name, 'email': contact.email}
            for contact in contacts
        ]
    except:
        contact_list = []
    
    context = {
        'total_rooms_count': total_rooms_count,
        'today_messages_count': today_messages_count,
        'online_users_count': 1,
        'contacts': contact_list,
    }
    return render(request, 'chat_app/email_compose.html', context)

@login_required
def email_api_inbox(request):
    """API endpoint for inbox emails - using real database"""
    try:
        # Get filter from request
        filter_type = request.GET.get('filter', 'inbox')
        
        # Base queryset
        if filter_type == 'inbox':
            emails_qs = Email.objects.filter(
                recipients=request.user,
                status='inbox'
            )
        elif filter_type == 'sent':
            emails_qs = Email.objects.filter(
                sender=request.user,
                status='sent'
            )
        elif filter_type == 'important':
            emails_qs = Email.objects.filter(
                recipients=request.user,
                status='inbox',
                is_starred=True
            )
        elif filter_type == 'trash':
            emails_qs = Email.objects.filter(
                Q(recipients=request.user) | Q(sender=request.user),
                status='trash'
            )
        elif filter_type == 'drafts':
            emails_qs = Email.objects.filter(
                sender=request.user,
                status='draft'
            )
        else:
            emails_qs = Email.objects.filter(
                recipients=request.user,
                status='inbox'
            )
        
        # Get emails with related data
        inbox_emails = emails_qs.select_related('sender').prefetch_related('attachments').order_by('-created_at')
        
        # Count unread emails (only for inbox)
        unread_count = 0
        if filter_type == 'inbox':
            unread_count = inbox_emails.filter(is_read=False).count()
        
        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = 20
        start = (page - 1) * per_page
        end = start + per_page
        
        # Prepare data
        emails_data = []
        for email in inbox_emails[start:end]:
            emails_data.append({
                'id': email.id,
                'sender': email.sender.username,
                'subject': email.subject or '(No Subject)',
                'preview': email.get_preview(100) if hasattr(email, 'get_preview') else (email.body[:100] + '...' if len(email.body) > 100 else email.body),
                'time': email.created_at.strftime('%I:%M %p') if email.created_at else '',
                'date': email.created_at.strftime('%b %d') if email.created_at else '',
                'unread': not email.is_read,
                'important': email.is_starred,
                'attachments': email.attachments.count(),
                'has_attachments': email.attachments.exists(),
            })
        
        return JsonResponse({
            'emails': emails_data,
            'unread_count': unread_count,
            'total_count': inbox_emails.count(),
            'page': page,
            'total_pages': (inbox_emails.count() + per_page - 1) // per_page,
            'filter': filter_type
        })
        
    except Exception as e:
        print(f"Error in email_api_inbox: {e}")  # For debugging
        # Fallback to dummy data if there's an error
        return get_dummy_email_data(request)

@login_required
def email_api_detail(request, email_id):
    """API endpoint for email detail - using real database"""
    try:
        email = Email.objects.get(
            Q(id=email_id, recipients=request.user) | 
            Q(id=email_id, sender=request.user, status__in=['sent', 'draft'])
        )
        
        # Mark as read if not already (only for inbox emails)
        if not email.is_read and email.status == 'inbox':
            email.mark_as_read()
        
        # Get attachments
        attachments = []
        for attachment in email.attachments.all():
            attachments.append({
                'id': attachment.id,
                'name': attachment.file_name,
                'size': attachment.file_size_display if hasattr(attachment, 'file_size_display') else f"{attachment.file_size} bytes",
                'url': attachment.file.url if attachment.file else '#',
                'type': attachment.file_type
            })
        
        # Get recipients info
        recipients_list = []
        for recipient in email.recipients.all():
            recipients_list.append({
                'username': recipient.username,
                'email': recipient.email
            })
        
        cc_list = []
        for cc in email.cc_recipients.all():
            cc_list.append({
                'username': cc.username,
                'email': cc.email
            })
        
        bcc_list = []
        for bcc in email.bcc_recipients.all():
            bcc_list.append({
                'username': bcc.username,
                'email': bcc.email
            })
        
        email_data = {
            'id': email.id,
            'sender': email.sender.username,
            'sender_email': email.sender.email,
            'subject': email.subject or '(No Subject)',
            'body': email.body,
            'body_html': email.body_html or email.body,
            'full_date': email.created_at.strftime('%B %d, %Y at %I:%M %p') if email.created_at else 'Unknown date',
            'important': email.is_starred,
            'read': email.is_read,
            'status': email.status,
            'attachments': attachments,
            'recipients': recipients_list,
            'cc': cc_list,
            'bcc': bcc_list,
            'can_reply': email.status == 'inbox',
            'can_forward': True,
            'can_delete': True,
        }
        
        return JsonResponse(email_data)
        
    except Email.DoesNotExist:
        return JsonResponse({
            'error': 'Email not found or you don\'t have permission to view it'
        }, status=404)
    except Exception as e:
        print(f"Error in email_api_detail: {e}")  # For debugging
        return get_dummy_email_detail(email_id)

@csrf_exempt
@login_required
def email_api_send(request):
    """API endpoint for sending emails - using real database"""
    if request.method == 'POST':
        try:
            recipient_emails = [email.strip() for email in request.POST.get('recipient', '').split(',') if email.strip()]
            cc_emails = [email.strip() for email in request.POST.get('cc', '').split(',') if email.strip()]
            bcc_emails = [email.strip() for email in request.POST.get('bcc', '').split(',') if email.strip()]
            subject = request.POST.get('subject', '').strip()
            body = request.POST.get('body', '').strip()
            body_html = request.POST.get('body_html', body)
            
            # Validate required fields
            if not recipient_emails:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'At least one recipient is required.'
                }, status=400)
            
            if not subject:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Subject is required.'
                }, status=400)
            
            if not body:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Message body is required.'
                }, status=400)
            
            # Validate email format
            import re
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            all_emails = recipient_emails + cc_emails + bcc_emails
            for email_addr in all_emails:
                if not re.match(email_regex, email_addr):
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Invalid email format: {email_addr}'
                    }, status=400)
            
            # Find or create users for recipients
            recipients = []
            cc_recipients = []
            bcc_recipients = []
            
            for email_addr in recipient_emails:
                user, created = User.objects.get_or_create(
                    email=email_addr,
                    defaults={'username': email_addr.split('@')[0], 'password': 'unusable'}
                )
                recipients.append(user)
            
            for email_addr in cc_emails:
                user, created = User.objects.get_or_create(
                    email=email_addr,
                    defaults={'username': email_addr.split('@')[0], 'password': 'unusable'}
                )
                cc_recipients.append(user)
            
            for email_addr in bcc_emails:
                user, created = User.objects.get_or_create(
                    email=email_addr,
                    defaults={'username': email_addr.split('@')[0], 'password': 'unusable'}
                )
                bcc_recipients.append(user)
            
            # Create the email for recipients (inbox)
            email = Email.objects.create(
                sender=request.user,
                subject=subject,
                body=body,
                body_html=body_html,
                status='inbox'
            )
            email.recipients.set(recipients)
            email.cc_recipients.set(cc_recipients)
            email.bcc_recipients.set(bcc_recipients)
            
            # Create sent copy for sender
            sent_email = Email.objects.create(
                sender=request.user,
                subject=subject,
                body=body,
                body_html=body_html,
                status='sent',
                is_read=True  # Sent emails are marked as read
            )
            sent_email.recipients.set(recipients)
            sent_email.cc_recipients.set(cc_recipients)
            sent_email.bcc_recipients.set(bcc_recipients)
            
            # Handle attachments
            if 'attachments' in request.FILES:
                for file in request.FILES.getlist('attachments'):
                    # Create attachment for recipient's email
                    attachment = EmailAttachment.objects.create(
                        email=email,
                        file=file,
                        file_name=file.name,
                        file_size=file.size,
                        file_type=file.content_type or 'application/octet-stream'
                    )
                    
                    # Create attachment for sent email
                    EmailAttachment.objects.create(
                        email=sent_email,
                        file=file,
                        file_name=file.name,
                        file_size=file.size,
                        file_type=file.content_type or 'application/octet-stream'
                    )
            
            # Create notifications for recipients
            try:
                from .models import EmailNotification
                for recipient in recipients:
                    EmailNotification.objects.create(
                        user=recipient,
                        notification_type='new_email',
                        email=email,
                        message=f'New email from {request.user.username}: {subject}'
                    )
            except:
                pass  # Notifications model might not exist yet
            
            return JsonResponse({
                'status': 'success', 
                'message': f'Email sent successfully to {len(recipients)} recipient(s)!',
                'email_id': email.id,
                'sent_email_id': sent_email.id
            })
            
        except Exception as e:
            import traceback
            print(f"Error in email_api_send: {e}")
            print(traceback.format_exc())
            return JsonResponse({
                'status': 'error', 
                'message': f'Error sending email: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error', 
        'message': 'Method not allowed. Use POST.'
    }, status=405)

@csrf_exempt
@login_required
def email_api_mark_read(request, email_id):
    """API endpoint for marking email as read - real implementation"""
    if request.method == 'POST':
        try:
            email = Email.objects.get(id=email_id, recipients=request.user)
            
            # Get action from request data
            import json
            data = json.loads(request.body) if request.body else {}
            action = data.get('action', 'read')  # 'read' or 'unread'
            
            if action == 'read':
                email.mark_as_read()
                message = f'Email #{email_id} marked as read.'
            else:
                email.mark_as_unread()
                message = f'Email #{email_id} marked as unread.'
            
            return JsonResponse({
                'status': 'success',
                'message': message,
                'is_read': email.is_read
            })
            
        except Email.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Email not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Method not allowed. Use POST.'
    }, status=405)

@csrf_exempt
@login_required
def email_api_toggle_star(request, email_id):
    """API endpoint for toggling star/important status"""
    if request.method == 'POST':
        try:
            email = Email.objects.get(id=email_id, recipients=request.user)
            email.toggle_star()
            
            return JsonResponse({
                'status': 'success',
                'message': f'Email #{email_id} {"starred" if email.is_starred else "unstarred"}',
                'is_starred': email.is_starred
            })
            
        except Email.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Email not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Method not allowed. Use POST.'
    }, status=405)

@csrf_exempt
@login_required
def email_api_delete(request, email_id):
    """API endpoint for deleting email - real implementation"""
    if request.method == 'POST':
        try:
            email = Email.objects.get(
                Q(id=email_id, recipients=request.user) | 
                Q(id=email_id, sender=request.user)
            )
            
            # Get action from request data
            import json
            data = json.loads(request.body) if request.body else {}
            permanent = data.get('permanent', False)
            
            if permanent:
                # Permanent delete
                email.delete()
                message = f'Email #{email_id} permanently deleted.'
            else:
                # Move to trash
                email.move_to_trash()
                message = f'Email #{email_id} moved to trash.'
            
            return JsonResponse({
                'status': 'success',
                'message': message
            })
            
        except Email.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Email not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Method not allowed. Use POST.'
    }, status=405)

@csrf_exempt
@login_required
def email_api_bulk_action(request):
    """API endpoint for bulk email actions"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body) if request.body else {}
            
            email_ids = data.get('email_ids', [])
            action = data.get('action', '')  # 'read', 'unread', 'star', 'unstar', 'delete', 'trash'
            
            if not email_ids:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No emails selected'
                }, status=400)
            
            # Get emails that belong to the user
            emails = Email.objects.filter(
                Q(id__in=email_ids, recipients=request.user) | 
                Q(id__in=email_ids, sender=request.user)
            )
            
            count = 0
            for email in emails:
                if action == 'read':
                    email.mark_as_read()
                    count += 1
                elif action == 'unread':
                    email.mark_as_unread()
                    count += 1
                elif action == 'star':
                    email.is_starred = True
                    email.save(update_fields=['is_starred'])
                    count += 1
                elif action == 'unstar':
                    email.is_starred = False
                    email.save(update_fields=['is_starred'])
                    count += 1
                elif action == 'delete':
                    email.delete()
                    count += 1
                elif action == 'trash':
                    email.move_to_trash()
                    count += 1
            
            return JsonResponse({
                'status': 'success',
                'message': f'{action.capitalize()} action applied to {count} email(s)',
                'count': count
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Method not allowed. Use POST.'
    }, status=405)

@login_required
def email_api_download(request, attachment_id):
    """API endpoint for downloading attachments"""
    try:
        attachment = EmailAttachment.objects.get(
            id=attachment_id,
            email__recipients=request.user
        )
        
        # In a real app, you'd serve the file
        # For now, return the URL
        return JsonResponse({
            'url': attachment.file.url if attachment.file else '#',
            'filename': attachment.file_name,
            'size': attachment.file_size_display if hasattr(attachment, 'file_size_display') else f"{attachment.file_size} bytes",
            'type': attachment.file_type,
            'message': 'Download link generated'
        })
        
    except EmailAttachment.DoesNotExist:
        return JsonResponse({
            'error': 'Attachment not found or you don\'t have permission to download it'
        }, status=404)

# Helper functions for fallback dummy data
def get_dummy_email_data(request):
    """Fallback dummy email data if database fails"""
    dummy_emails = [
        {
            'id': 1,
            'sender': 'admin',
            'subject': 'Welcome to Chat Application',
            'preview': 'Welcome to our chat platform! We hope you enjoy using all our features including group chats, direct messages, and AI assistant...',
            'time': '10:00 AM',
            'date': timezone.now().strftime('%b %d'),
            'unread': True,
            'important': False,
            'attachments': 0,
            'has_attachments': False,
        },
        # ... (keep your existing dummy emails)
    ]
    
    return JsonResponse({
        'emails': dummy_emails,
        'unread_count': 2,
        'total_count': len(dummy_emails),
        'page': 1,
        'total_pages': 1,
        'filter': 'inbox',
        'note': 'Using dummy data - database might not be ready'
    })

def get_dummy_email_detail(email_id):
    """Fallback dummy email detail if database fails"""
    email_details = {
        1: {
            'id': 1,
            'sender': 'admin',
            'sender_email': 'admin@chat-app.com',
            'subject': 'Welcome to Chat Application',
            'body': '''<p>Dear User,</p>
                      <p>Welcome to Chat Application! We\'re excited to have you on board.</p>
                      <p>Our platform offers a comprehensive set of features:</p>
                      <ul>
                        <li>Real-time group chats</li>
                        <li>Direct messaging</li>
                        <li>AI Assistant powered by Groq</li>
                        <li>Email system (you\'re looking at it!)</li>
                        <li>User profiles and settings</li>
                      </ul>
                      <p>Feel free to explore all the features and let us know if you have any questions.</p>
                      <p>Best regards,<br>The Chat Application Team</p>''',
            'full_date': timezone.now().strftime('%B %d, %Y at %I:%M %p'),
            'important': False,
            'read': False,
            'attachments': []
        },
        # ... (keep your existing dummy email details)
    }
    
    email_data = email_details.get(email_id, {
        'id': email_id,
        'sender': 'System',
        'sender_email': 'system@chat-app.com',
        'subject': f'Email #{email_id}',
        'body': 'This is a sample email body.',
        'full_date': timezone.now().strftime('%B %d, %Y at %I:%M %p'),
        'important': False,
        'read': True,
        'attachments': [],
        'note': 'Using dummy data - database might not be ready'
    })
    
    return JsonResponse(email_data)