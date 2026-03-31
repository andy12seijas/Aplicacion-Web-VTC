# auth_backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User

class PerfilActivoBackend(ModelBackend):
    """
    Backend de autenticación que verifica que el perfil del usuario esté activo
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                # Verificar si el perfil existe y está activo
                if hasattr(user, 'perfil') and not user.perfil.activo:
                    return None
                # Si no tiene perfil (por si acaso), también rechazar
                if not hasattr(user, 'perfil'):
                    return None
                return user
        except User.DoesNotExist:
            return None
        return None
    
    def get_user(self, user_id):
        try:
            user = User.objects.get(pk=user_id)
            # Verificar si el perfil existe y está activo
            if hasattr(user, 'perfil') and not user.perfil.activo:
                return None
            if not hasattr(user, 'perfil'):
                return None
            return user
        except User.DoesNotExist:
            return None