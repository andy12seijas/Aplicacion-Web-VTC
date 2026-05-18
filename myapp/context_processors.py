# myapp/context_processors.py
import pytz
from django.utils import timezone

def zona_horaria_venezuela(request):
    """
    Context processor para activar la zona horaria de Venezuela
    en TODAS las vistas automáticamente.
    """
    # Activar zona horaria de Venezuela para toda la sesión
    timezone.activate(pytz.timezone('America/Caracas'))
    return {}