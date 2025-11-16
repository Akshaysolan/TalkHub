from django.urls import path
from . import views

app_name = 'chat_app'

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('create_room/', views.create_room, name='create_room'),
    path('room/<str:room_name>/', views.room, name='room'),
    path('direct-messages/', views.direct_messages, name='direct_messages'),
    path('group-chats/', views.group_chats, name='group_chats'),
    path('favorites/', views.favorites, name='favorites'),
    path('settings/', views.settings, name='settings'),
    path('api/messages/<str:room_name>/', views.get_messages, name='get_messages'),
    
    path('dm/<str:username>/', views.direct_message_chat, name='direct_message_chat'),
    path('dm/send/<str:username>/', views.send_direct_message, name='send_direct_message'),
    path('dm/get/<str:username>/', views.get_direct_messages, name='get_direct_messages'),
    path('user-search/', views.user_search, name='user_search'),
    
    path('ai-assistant/', views.ai_assistant_view, name='ai_assistant'),
    path('ai-chat/', views.ai_chat_api, name='ai_chat_api'),


    # AI / chat session endpoints
    path('ai-assistant/', views.ai_assistant_view, name='ai_assistant'),
    path('ai/api/chat/', views.ai_chat_api, name='ai_chat_api'),            # send message (existing)
    path('ai/api/sessions/', views.ai_sessions_list, name='ai_sessions_list'),   # GET list, POST create
    path('ai/api/sessions/<int:session_id>/', views.ai_session_detail, name='ai_session_detail'),  # GET session messages
    path('ai/api/sessions/<int:session_id>/delete/', views.ai_delete_session, name='ai_delete_session'),
    path('ai/api/sessions/delete_all/', views.ai_delete_all_sessions, name='ai_delete_all_sessions'),

    path('groups/', views.group_chats, name='group_chats'),
    path('groups/create/', views.create_group, name='create_group'),
    path('groups/<str:room_name>/', views.start_group_chat, name='start_group_chat'),


]
