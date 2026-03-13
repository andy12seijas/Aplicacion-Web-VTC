from django.shortcuts import render, redirect,HttpResponse
from django.contrib.auth import authenticate, login
from django.contrib import messages
#Funcion para enviar los datos para iniciar sesion
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')  
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'Inicio_De_Sesion/login.html')


#Funcion para mostrar el dashboard despues de iniciar sesion

def dashboard(request):
    return render(request, 'Inicio_De_Sesion/dashboard.html')


