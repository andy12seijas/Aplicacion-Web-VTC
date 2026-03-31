from django.shortcuts import render

# Create your views here.
# views.py (o donde tengas tu vista de login)

from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib.auth.models import User

class CustomLoginView(LoginView):
    template_name = 'Admin/login.html'
    
    def form_invalid(self, form):
        # Verificar si el usuario existe
        username = form.cleaned_data.get('username')
        try:
            user = User.objects.get(username=username)
            
            # Verificar si el perfil está desactivado
            if hasattr(user, 'perfil') and not user.perfil.activo:
                messages.error(self.request, '❌ Su cuenta ha sido desactivada. Por favor, contacte al administrador.')
                return redirect('login')
            
            # Verificar si el usuario está inactivo (is_active=False)
            if not user.is_active:
                messages.error(self.request, '❌ Su cuenta está desactivada. Por favor, contacte al administrador.')
                return redirect('login')
                
        except User.DoesNotExist:
            pass
        
        messages.error(self.request, '❌ Usuario o contraseña incorrectos.')
        return super().form_invalid(form)
    
    def form_valid(self, form):
        # Verificación adicional antes de iniciar sesión
        user = form.get_user()
        
        if hasattr(user, 'perfil') and not user.perfil.activo:
            messages.error(self.request, '❌ Su cuenta ha sido desactivada. Por favor, contacte al administrador.')
            return redirect('login')
        
        if not user.is_active:
            messages.error(self.request, '❌ Su cuenta está desactivada. Por favor, contacte al administrador.')
            return redirect('login')
        
        return super().form_valid(form)