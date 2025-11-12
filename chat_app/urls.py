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
    path('api/messages/<str:room_name>/', views.get_messages, name='get_messages'),
]