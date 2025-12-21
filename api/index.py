import os
import sys
from django.core.wsgi import get_wsgi_application

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chat_project.settings")

application = get_wsgi_application()


def handler(request, response):
    response.status_code = 200
    response.set_header("Content-Type", "text/html")
    
    
    django_response = application(request, {})
    
    
    response.status_code = django_response.status_code
    
   
    for header, value in django_response.items():
        response.set_header(header, value)
    
    
    response.send(django_response.content)