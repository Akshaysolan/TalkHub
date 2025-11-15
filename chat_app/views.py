from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from .models import Room, Message, DirectMessage
from django.contrib.auth.models import User
from django.db.models import Q, Max, Count

from .ai_chat import ask_gemini
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.http import JsonResponse
import google.generativeai as genai
import os

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


genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@csrf_exempt
@login_required
def ai_assistant_view(request):
    if request.method == "POST":
        user_message = request.POST.get("message", "")
        if not user_message:
            return JsonResponse({"reply": "Message cannot be empty."})

        ai_response = ask_gemini(user_message)
        return JsonResponse({"reply": ai_response})

    return render(request, "chat_app/ai_assistant.html")
