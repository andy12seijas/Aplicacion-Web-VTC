from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def admin_required(view_func):
    """Decorador para permitir solo a superusuarios y administradores"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_superuser or request.user.groups.filter(name='Administrador').exists():
            return view_func(request, *args, **kwargs)
        messages.error(request, '⛔ Acceso denegado. Solo administradores pueden acceder a esta página.')
        return redirect('lista_clientes')
    return _wrapped_view