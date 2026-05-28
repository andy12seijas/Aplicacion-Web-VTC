from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from .models import ModeloModem
from .forms import ModeloModemForm

# Listar modelos
@login_required
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Administrador').exists())
def lista_modelos_modem(request):
    modelos = ModeloModem.objects.all()
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        modelos = modelos.filter(nombre__icontains=search)
    
    # Paginación
    paginator = Paginator(modelos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_count': modelos.count(),
        'search': search,
    }
    return render(request, 'modem/ver_modem.html', context)


# Crear y Editar (misma template)
@login_required
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Administrador').exists())
def crear_editar_modelo_modem(request, id=None):
    if id:
        modelo = get_object_or_404(ModeloModem, id=id)
        titulo = "Editar Modelo de Módem"
        boton_texto = "Actualizar"
    else:
        modelo = None
        titulo = "Nuevo Modelo de Módem"
        boton_texto = "Guardar"
    
    if request.method == 'POST':
        form = ModeloModemForm(request.POST, instance=modelo)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Modelo guardado exitosamente.')
            return redirect('lista_modelos_modem')
    else:
        form = ModeloModemForm(instance=modelo)
    
    context = {
        'form': form,
        'titulo': titulo,
        'boton_texto': boton_texto,
    }
    return render(request, 'modem/crear_modem.html', context)