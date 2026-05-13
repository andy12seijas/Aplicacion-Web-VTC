from django.shortcuts import render, redirect,HttpResponse
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.models import User
#Funcion para enviar los datos para iniciar sesion

from django.shortcuts import render

def landing_page(request):
    """Vista principal del landing page"""
    return render(request, 'landing/index.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Primero verificar si el usuario existe
        try:
            user = User.objects.get(username=username)
            
            # Verificar si el perfil está desactivado
            if hasattr(user, 'perfil') and not user.perfil.activo:
                messages.error(request, 'Su cuenta ha sido desactivada. Por favor, contacte al administrador.')
                return render(request, 'Inicio_De_Sesion/login.html')
            
            # Verificar si el usuario está inactivo en Django
            if not user.is_active:
                messages.error(request, 'Su cuenta está desactivada. Por favor, contacte al administrador.')
                return render(request, 'Inicio_De_Sesion/login.html')
                
        except User.DoesNotExist:
            pass  # El usuario no existe, se mostrará el error de autenticación
        
        # Autenticar usuario
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, '❌ Usuario o contraseña incorrectos')
            return render(request, 'Inicio_De_Sesion/login.html')
    
    return render(request, 'Inicio_De_Sesion/login.html')

#Funcion para mostrar el dashboard despues de iniciar sesion




