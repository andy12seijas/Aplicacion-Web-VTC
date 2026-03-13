from email.headerregistry import Group
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from .models import ClientePotencial
from .forms import ClientePotencialForm
from django.contrib.auth.models import User, Group 
from .decorators import admin_required
from myapp.models import *


# ============================================
# VISTA PARA LISTAR CLIENTES
# ============================================
@login_required
def lista_clientes(request):
    """Lista todos los clientes potenciales con filtros y búsqueda"""
    
    # 👥 DETERMINAR SI ES ADMIN (definir al principio)
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    # Base query - todos los clientes
    clientes = ClientePotencial.objects.all().select_related('creado_por')
    
    # Si no es admin, solo ve sus propios clientes
    if not es_admin:
        clientes = clientes.filter(creado_por=request.user)
    
    # ===== FILTROS =====
    # Filtro por búsqueda (nombre, apellido, cédula, teléfono)
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        clientes = clientes.filter(
            Q(cedula__icontains=busqueda) |
            Q(nombre__icontains=busqueda) |
            Q(apellido__icontains=busqueda) |
            Q(telefono__icontains=busqueda) |
            Q(direccion__icontains=busqueda)
        )
    
    # Filtro por nivel de interés
    interes = request.GET.get('interes', '')
    if interes:
        clientes = clientes.filter(interesado=interes)
    
    # Filtro por posee internet
    internet = request.GET.get('internet', '')
    if internet == 'si':
        clientes = clientes.filter(posee_internet=True)
    elif internet == 'no':
        clientes = clientes.filter(posee_internet=False)
    
    # FILTRO POR VENDEDOR (solo para administradores)
    vendedor_filtro = request.GET.get('vendedor', '')
    if vendedor_filtro and es_admin:
        clientes = clientes.filter(creado_por__username=vendedor_filtro)
    
    # Filtro por rango de fechas
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    if fecha_desde:
        clientes = clientes.filter(fecha_registro__gte=fecha_desde)
    if fecha_hasta:
        clientes = clientes.filter(fecha_registro__lte=fecha_hasta)
    
    # ===== ESTADÍSTICAS =====
    total_clientes = clientes.count()
    interesados = clientes.filter(interesado='SI').count()
    tal_vez = clientes.filter(interesado='TAL_VEZ').count()
    no_interesados = clientes.filter(interesado='NO').count()
    con_internet = clientes.filter(posee_internet=True).count()
    sin_internet = clientes.filter(posee_internet=False).count()
    
    # Clientes registrados hoy
    hoy = timezone.now().date()
    clientes_hoy = clientes.filter(fecha_registro=hoy).count()
    
    # Clientes de esta semana
    semana_pasada = hoy - timedelta(days=7)
    clientes_semana = clientes.filter(fecha_registro__gte=semana_pasada).count()
    
    # ===== LISTA DE VENDEDORES PARA EL FILTRO (solo para admin) =====
    vendedores = []
    if es_admin:
        # 🔥 CAMBIO AQUÍ: TODOS los usuarios del sistema
        vendedores = User.objects.all().order_by('username')
    
    # ===== PAGINACIÓN =====
    paginator = Paginator(clientes, 15)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    
    context = {
        'page_obj': page_obj,
        'busqueda': busqueda,
        'interes_seleccionado': interes,
        'internet_seleccionado': internet,
        'vendedor_filtro': vendedor_filtro,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        # Estadísticas
        'total_clientes': total_clientes,
        'interesados': interesados,
        'tal_vez': tal_vez,
        'no_interesados': no_interesados,
        'con_internet': con_internet,
        'sin_internet': sin_internet,
        'clientes_hoy': clientes_hoy,
        'clientes_semana': clientes_semana,
        'es_admin': es_admin,
        'vendedores': vendedores,  # ✅ Ahora son TODOS los usuarios
    }
    return render(request, 'Vendedores/lista_clientes.html', context)

@login_required
def crear_cliente(request):
    """Crea un nuevo cliente potencial"""
    
    if request.method == 'POST':
        form = ClientePotencialForm(request.POST, es_creacion=True)
        if form.is_valid():
            cliente = form.save(commit=False)
            # Asignar el usuario actual como creador
            cliente.creado_por = request.user
            cliente.save()
            
             # 2. ACTUALIZAR la ubicación del usuario
            latitud = request.POST.get('latitud')
            longitud = request.POST.get('longitud')
            
            if latitud and longitud:
                # Crear texto asociado para referencia
                contenido = f"Cliente: {cliente.nombre} {cliente.apellido}"
                
                # Actualizar o crear ubicación
                UbicacionUsuario.objects.update_or_create(
                    usuario=request.user,
                    defaults={
                        'latitud': float(latitud),
                        'longitud': float(longitud),
                        'contenido_asociado': contenido,
                    }
                )
            
            messages.success(
                request, 
                f'✅ Cliente {cliente.nombre_completo} (C.I: {cliente.cedula}) creado exitosamente.'
            )
            return redirect('lista_clientes')
        else:
            messages.error(
                request,
                '❌ Error al crear el cliente. Por favor revise los campos.'
            )
    else:
        form = ClientePotencialForm(es_creacion=True)
    
    # Obtener la fecha actual para el template
    today = timezone.now().date()
    
    return render(request, 'Vendedores/crear_clientes.html', {
        'form': form,
        'titulo': 'Nuevo Cliente Potencial',
        'subtitulo': 'Registrar nuevo cliente en el sistema',
        'boton_texto': 'Guardar Cliente',
        'es_creacion': True,
        'today': today,  # 👈 IMPORTANTE: pasar today al template
    })

    
    
    
@login_required
def verificar_cedula(request, cedula):
    """Verifica si una cédula ya está registrada"""
    try:
        cliente = ClientePotencial.objects.select_related('creado_por').get(cedula=cedula)
        data = {
            'existe': True,
            'cliente': {
                'nombre': cliente.nombre,
                'apellido': cliente.apellido,
                'telefono': cliente.telefono,
                'fecha_registro': cliente.fecha_registro.strftime('%d/%m/%Y'),
                'creado_por': cliente.creado_por.username if cliente.creado_por else 'Sistema'
            }
        }
    except ClientePotencial.DoesNotExist:
        data = {'existe': False}
    
    return JsonResponse(data)    


@login_required
def datos_cliente(request, cliente_id):
    """API para obtener datos de un cliente en formato JSON"""
    
    cliente = get_object_or_404(ClientePotencial, id=cliente_id)
    
    # Verificar permisos
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    if not (es_admin or cliente.creado_por == request.user):
        return JsonResponse({'error': 'No tienes permiso para ver este cliente'}, status=403)
    
    # Calcular días desde registro
    dias_desde_registro = (timezone.now().date() - cliente.fecha_registro).days
    today = timezone.now().date()
    data = {
        'id': cliente.id,
        'nombre': cliente.nombre,
        'apellido': cliente.apellido,
        'cedula': cliente.cedula,
        'telefono': cliente.telefono,
        'direccion': cliente.direccion,
        'interesado': cliente.interesado,
        'get_interesado_display': cliente.get_interesado_display(),
        'posee_internet': cliente.posee_internet,
        'fecha_registro': cliente.fecha_registro.strftime('%d/%m/%Y'),
        'creado_por': cliente.creado_por.get_full_name() or cliente.creado_por.username if cliente.creado_por else 'Sistema',
        'dias_desde_registro': dias_desde_registro,
        'observacion': cliente.observacion,
        'today': today,
    }
    
    return JsonResponse(data)


@login_required
@admin_required
def editar_cliente(request, cliente_id):
    """Edita un cliente existente - Solo para superuser y administradores"""
    
    # Verificar si el usuario es superuser o administrador
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()):
        # Opción 1: Redirigir con mensaje de error
        messages.error(request, '⛔ Acceso denegado. Solo administradores pueden editar clientes.')
        return redirect('lista_clientes')
        
        # Opción 2: Lanzar error 403 (Forbidden)
        # raise PermissionDenied
    
    cliente = get_object_or_404(ClientePotencial, id=cliente_id)
    
    if request.method == 'POST':
        form = ClientePotencialForm(request.POST, instance=cliente, es_creacion=False)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'✅ Cliente {cliente.nombre_completo} actualizado correctamente.'
            )
            return redirect('lista_clientes')
        else:
            messages.error(
                request,
                '❌ Error al actualizar el cliente. Por favor revise los campos.'
            )
    else:
        form = ClientePotencialForm(instance=cliente, es_creacion=False)
    
    return render(request, 'Vendedores/crear_clientes.html', {
        'form': form,
        'titulo': 'Editar Cliente',
        'subtitulo': f'Modificando datos de {cliente.nombre_completo}',
        'boton_texto': 'Actualizar Cliente',
        'es_creacion': False,
        'cliente': cliente
    })