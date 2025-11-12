from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.http import JsonResponse
from .models import Room, Message
import json

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
    rooms = Room.objects.all().prefetch_related('messages')
    return render(request, 'chat_app/index.html', {'rooms': rooms})

@login_required
def room(request, room_name):
    room_obj = get_object_or_404(Room, name=room_name)
    messages = Message.objects.filter(room=room_obj).select_related('user')[:50]
    return render(request, 'chat_app/room.html', {
        'room': room_obj,
        'messages': messages
    })

@login_required
def create_room(request):
    if request.method == 'POST':
        room_name = request.POST.get('room_name')
        if room_name:
            room_obj, created = Room.objects.get_or_create(name=room_name)
            return redirect('chat_app:room', room_name=room_obj.name)
    return redirect('chat_app:index')

@login_required
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