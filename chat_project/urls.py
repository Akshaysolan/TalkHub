"""
URL configuration for chat_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.http import HttpResponse

def websocket_test(request):
    return HttpResponse("""
    <html>
    <body>
        <h1>WebSocket Test</h1>
        <div id="status">Testing WebSocket...</div>
        <script>
            const ws = new WebSocket('ws://' + window.location.host + '/ws/chat/test/');
            ws.onopen = function() {
                document.getElementById('status').textContent = 'WebSocket CONNECTED!';
            };
            ws.onerror = function(e) {
                document.getElementById('status').textContent = 'WebSocket ERROR: ' + e;
            };
            ws.onclose = function() {
                document.getElementById('status').textContent = 'WebSocket CLOSED';
            };
        </script>
    </body>
    </html>
    """)

def redirect_to_login(request):
    return redirect('chat_app:login')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('chat_app.urls')),
    path('websocket-test/', websocket_test, name='websocket_test'),
]