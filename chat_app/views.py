from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from .models import Room, Message, DirectMessage
from django.contrib.auth.models import User
from django.db.models import Q, Max, Count
from django.contrib import messages
import json

import os
from .ai_chat import ask_gemini
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.http import JsonResponse
import google.generativeai as genai
from groq import Groq

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

@login_required
def direct_messages(request):
    return render(request, 'chat_app/direct_messages.html', {
        'dm_conversations': [],
    })

@login_required
def group_chats(request):
    user_rooms = Room.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'chat_app/group_chats.html', {
        'user_rooms': user_rooms,
    })

@login_required
def favorites(request):
    return render(request, 'chat_app/favorites.html', {
        'favorite_rooms': [],
    })

@login_required
def settings(request):
    return render(request, 'chat_app/settings.html', {
        'profile': None,
    })

# Remove complex views for now
def toggle_favorite(request, room_name):
    return JsonResponse({'status': 'error', 'is_favorited': False})

def direct_message_chat(request, username):
    return render(request, 'chat_app/direct_message_chat.html', {
        'other_user': get_object_or_404(User, username=username),
        'messages': [],
    })

def send_direct_message(request, username):
    return JsonResponse({'status': 'error', 'message': 'Feature not available'})

def user_search(request):
    return JsonResponse([], safe=False)

def get_messages(request, room_name):
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


@login_required
def direct_messages(request):
    """
    List user's DM conversations:
    For each other user we compute last_message and unread_count.
    """
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

    return render(request, 'chat_app/direct_messages.html', {
        'dm_conversations': conversations,
    })


@login_required
def direct_message_chat(request, username):
    """
    Render chat view between request.user and username.
    """
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

    # Prepare messages list for template (you already have a messages variable in template)
    return render(request, 'chat_app/direct_message_chat.html', {
        'other_user': other_user,
        'messages': messages,
    })


@login_required
def send_direct_message(request, username):
    """
    Accepts POST (AJAX or normal) to send a DM to username.
    Returns JSON {status: 'success', message: {...}} or error JSON.
    """
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
def user_search(request):
    """
    GET ?q=... -> JSON list of users matching q (exclude request.user)
    """
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
def get_direct_messages(request, username):
    """
    Return last N messages between request.user and username as JSON.
    Useful for polling.
    """
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


# # Load Groq API Key
# client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# def ask_ai(message):
#     try:
#         response = client.chat.completions.create(
#             model="llama-3.3-70b-versatile",
#             messages=[{"role": "user", "content": message}]
#         )
#         return response.choices[0].message.content
#     except Exception as e:
#         return f"Error: {str(e)}"


# @login_required
# def ai_assistant_view(request):
#     return render(request, "chat_app/ai_assistant.html")


# @csrf_exempt
# @login_required
# def ai_chat_api(request):
#     if request.method == "POST":
#         user_msg = request.POST.get("message", "")
#         if not user_msg:
#             return JsonResponse({"reply": "Message cannot be empty!"})

#         ai_reply = ask_ai(user_msg)
#         return JsonResponse({"reply": ai_reply})

#     return JsonResponse({"error": "Invalid request"}, status=400)


import os
import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from groq import Groq

from .models import ChatSession, ChatMessage

# configure groq client (use env var)
GROQ_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

def ask_groq(message):
    """
    Call Groq chat completion and return assistant text.
    Important: Groq returns objects, so use dot-notation: .message.content
    """
    if client is None:
        return "AI not configured (GROQ_API_KEY missing)."

    try:
        resp = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            messages=[{"role": "user", "content": message}]
        )

        # CORRECT: use dot access, not dict indexing
        # e.g. resp.choices[0].message.content
        # protect against unexpected shape:
        choice = getattr(resp.choices[0], "message", None)
        if choice is None:
            # fallback: try the older style if available
            return str(resp)
        return choice.content

    except Exception as e:
        # return readable error for frontend
        return f"Error: {str(e)}"


@login_required
def ai_assistant_view(request):
    # main page
    return render(request, 'chat_app/ai_assistant.html', {})


@csrf_exempt
@login_required
def ai_chat_api(request):
    # send message -> returns AI reply and stores both messages
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
    # GET: return list of sessions, POST: create empty session
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
    # GET messages for session
    s = get_object_or_404(ChatSession, id=session_id, user=request.user)
    msgs = s.messages.all().values("id", "sender", "content", "timestamp")
    return JsonResponse(list(msgs), safe=False)


@login_required
def ai_delete_session(request, session_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)
    s = get_object_or_404(ChatSession, id=session_id, user=request.user)
    s.delete()
    return JsonResponse({"deleted": True})


@login_required
def ai_delete_all_sessions(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)
    ChatSession.objects.filter(user=request.user).delete()
    return JsonResponse({"deleted_all": True})


@login_required
def group_chats(request):
    """Display user's group chats"""
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


#####
# Add these imports at the top
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .models import Profile  # Add this import

# ... your other imports ...

# Replace your current settings view with this:
@login_required
def settings(request):
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
    
    if request.method == 'POST':
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return handle_ajax_request(request, profile)
        else:
            return handle_regular_request(request, profile)
    
    return render(request, 'chat_app/settings.html', {
        'profile': profile
    })

def handle_ajax_request(request, profile):
    """Handle AJAX form submission"""
    try:
        # Get form data
        email = request.POST.get('email', '').strip()
        bio = request.POST.get('bio', '').strip()
        
        response_data = {}
        
        # Validate and update email if changed
        if email and email != request.user.email:
            # Validate email format
            validate_email(email)
            
            # Check if email already exists (excluding current user)
            from django.contrib.auth.models import User
            if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                return JsonResponse({
                    'success': False,
                    'message': 'This email is already registered with another account.'
                })
            
            # Update email
            request.user.email = email
            request.user.save()
            response_data['new_email'] = request.user.email
        
        # Update bio if profile is a model instance
        if hasattr(profile, 'save'):
            profile.bio = bio
            profile.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully!',
            **response_data
        })
        
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'message': 'Please enter a valid email address.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        })

def handle_regular_request(request, profile):
    """Handle regular form submission (non-AJAX)"""
    try:
        email = request.POST.get('email', '').strip()
        bio = request.POST.get('bio', '').strip()
        
        # Update bio if profile is a model instance
        if hasattr(profile, 'save') and bio != getattr(profile, 'bio', ''):
            profile.bio = bio
            profile.save()
            messages.success(request, 'Bio updated successfully!')
        
        # Update email if changed
        if email and email != request.user.email:
            try:
                validate_email(email)
                
                # Check if email exists
                from django.contrib.auth.models import User
                if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                    messages.error(request, 'This email is already registered with another account.')
                else:
                    request.user.email = email
                    request.user.save()
                    messages.success(request, 'Email updated successfully!')
                    
            except ValidationError:
                messages.error(request, 'Please enter a valid email address.')
        
        return redirect('chat_app:settings')
        
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
        return redirect('chat_app:settings')