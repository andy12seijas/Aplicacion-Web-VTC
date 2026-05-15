# middleware.py

from django.utils import timezone
import pytz

class ZonaHorariaMiddleware:
    """Middleware para forzar zona horaria de Venezuela a todos los usuarios"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Forzar zona horaria de Venezuela
        timezone.activate(pytz.timezone('America/Caracas'))
        return self.get_response(request)