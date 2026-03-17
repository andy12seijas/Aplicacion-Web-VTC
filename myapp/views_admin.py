import json
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.core.paginator import Paginator
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q
from myapp.models import ClientePotencial
from .forms import *
from django.contrib.auth import logout
from django.utils import timezone
from datetime import timedelta

# Verificar si es administrador
def es_administrador(user):
    return user.groups.filter(name='Administrador').exists() or user.is_superuser


@user_passes_test(es_administrador)
@login_required
def lista_usuarios(request):
    """Solo administradores pueden ver la lista de usuarios"""
    usuarios = User.objects.all().order_by('-date_joined')
    
    # Estadísticas por rol
    total_usuarios = usuarios.count()
    usuarios_activos = usuarios.filter(is_active=True).count()
    
    admin_group = Group.objects.get(name='Administrador')
    vendedor_group = Group.objects.get(name='Vendedor')
    instalador_group = Group.objects.get(name='Instalador')
    
    total_administradores = admin_group.user_set.count()
    total_vendedores = vendedor_group.user_set.count()
    total_instaladores = instalador_group.user_set.count()
    total_superusuarios = User.objects.filter(is_superuser=True).count()
    
    paginator = Paginator(usuarios, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_usuarios': total_usuarios,
        'usuarios_activos': usuarios_activos,
        'total_administradores': total_administradores,
        'total_vendedores': total_vendedores,
        'total_instaladores': total_instaladores,
        'total_superusuarios': total_superusuarios,
    }
    
    return render(request, 'Admin/ver_usuario.html', context)



@permission_required('auth.add_user', raise_exception=True)
@login_required
def crear_usuario(request):
    """Solo usuarios con permiso pueden crear usuarios"""
    if request.method == 'POST':
        form = UsuarioForm(request.POST, es_creacion=True)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Usuario "{user.username}" creado exitosamente.')
            return redirect('lista_usuarios')
    else:
        form = UsuarioForm(es_creacion=True)
    
    context = {
        'form': form,
        'titulo': 'Crear Usuario',
        'subtitulo': 'Registrar nuevo usuario en el sistema',
        'boton_texto': 'Crear Usuario',
        'es_creacion': True,
    }
    
    return render(request, 'Admin/crear_usuario.html', context)


@permission_required('auth.change_user', raise_exception=True)
@login_required
def editar_usuario(request, user_id):
    """Solo usuarios con permiso pueden editar usuarios"""
    usuario = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=usuario, es_creacion=False)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Usuario "{user.username}" actualizado exitosamente.')
            return redirect('lista_usuarios')
    else:
        form = UsuarioForm(instance=usuario, es_creacion=False)
    
    context = {
        'form': form,
        'titulo': 'Editar Usuario',
        'subtitulo': f'Modificando datos de {usuario.username}',
        'boton_texto': 'Actualizar Usuario',
        'es_creacion': False,
        'usuario': usuario,
    }
    
    return render(request, 'Admin/crear_usuario.html', context)


@login_required
@permission_required('auth.delete_user', raise_exception=True)
def cambiar_estado_usuario(request, user_id):
    """Activar/Desactivar usuario"""
    if request.method == 'POST':
        usuario = get_object_or_404(User, id=user_id)
        usuario.is_active = not usuario.is_active
        usuario.save()
        estado = "activado" if usuario.is_active else "desactivado"
        messages.success(request, f'Usuario "{usuario.username}" {estado} exitosamente.')
    return redirect('lista_usuarios')


def logout_view(request):
    """Cierra la sesión del usuario"""
    logout(request)
    messages.success(request, 'Sesión cerrada exitosamente.')
    return redirect('login')

@login_required
def mapa_usuarios(request):
    """Vista para administradores - Mapa con ubicación ACTUAL de usuarios"""
    
    # Verificar permisos
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()):
        messages.error(request, '⛔ Acceso denegado. Solo administradores.')
        return redirect('lista_clientes')
    
    # Obtener filtros de la URL
    tipo_usuario = request.GET.get('tipo', 'todos')
    buscar = request.GET.get('buscar', '')
    
    # Base query
    ubicaciones = UbicacionUsuario.objects.select_related('usuario').all()
    
    # Filtrar por tipo de usuario (grupo)
    if tipo_usuario and tipo_usuario != 'todos':
        ubicaciones = ubicaciones.filter(usuario__groups__name=tipo_usuario)
    
    # Filtrar por búsqueda
    if buscar:
        ubicaciones = ubicaciones.filter(
            Q(usuario__username__icontains=buscar) |
            Q(usuario__first_name__icontains=buscar) |
            Q(usuario__last_name__icontains=buscar)
        )
    
    # Preparar datos para el mapa
    datos_mapa = []
    for ubicacion in ubicaciones:
        # Obtener el grupo del usuario
        grupo = ubicacion.usuario.groups.first()
        tipo = grupo.name if grupo else 'Sin grupo'
        
        # Calcular total de clientes del usuario
        total_clientes = ClientePotencial.objects.filter(creado_por=ubicacion.usuario).count()
        
        datos_mapa.append({
            'usuario': {
                'id': ubicacion.usuario.id,
                'username': ubicacion.usuario.username,
                'first_name': ubicacion.usuario.first_name,
                'last_name': ubicacion.usuario.last_name,
                'tipo': tipo,
            },
            'latitud': ubicacion.latitud,
            'longitud': ubicacion.longitud,
            'ultima_actualizacion': ubicacion.ultima_actualizacion.isoformat(),
            'activo': ubicacion.esta_activo,
            'total_clientes': total_clientes,
        })
    
    # Estadísticas
    hace_1hora = timezone.now() - timedelta(hours=1)
    activos_ahora = ubicaciones.filter(ultima_actualizacion__gte=hace_1hora).count()
    
    # Estadísticas por tipo
    from django.contrib.auth.models import Group
    stats_por_tipo = []
    for grupo in Group.objects.all():
        count = ubicaciones.filter(usuario__groups=grupo).count()
        if count > 0:
            stats_por_tipo.append({
                'nombre': grupo.name,
                'cantidad': count,
            })
    
    context = {
        'ubicaciones': datos_mapa,
        'total_usuarios': ubicaciones.count(),
        'activos_ahora': activos_ahora,
        'stats_por_tipo': stats_por_tipo,
        'filtro_tipo': tipo_usuario,
        'buscar': buscar,
    }
    
    return render(request, 'admin/mapa_usuarios.html', context)



@login_required
def panel_administrativo(request):
    """Vista del panel administrativo con botones de acceso rápido"""
    
    # Verificar que solo administradores puedan acceder
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()):
        messages.error(request, '⛔ Acceso denegado. Solo administradores.')
        return redirect('dashboard')  # o donde quieras redirigir
    
    from django.contrib.auth.models import User, Group
    
    # Estadísticas para mostrar
    total_usuarios = User.objects.filter(is_active=True).count()
    
    try:
        total_vendedores = Group.objects.get(name='Vendedor').user_set.filter(is_active=True).count()
    except Group.DoesNotExist:
        total_vendedores = 0
    
    try:
        total_instaladores = Group.objects.get(name='Instalador').user_set.filter(is_active=True).count()
    except Group.DoesNotExist:
        total_instaladores = 0
    
    try:
        total_administradores = Group.objects.get(name='Administrador').user_set.filter(is_active=True).count()
    except Group.DoesNotExist:
        total_administradores = 0
    
    context = {
        'total_usuarios': total_usuarios,
        'total_vendedores': total_vendedores,
        'total_instaladores': total_instaladores,
        'total_administradores': total_administradores,
    }
    
    return render(request, 'Admin/panel_administrativo.html', context)


@login_required
def gestionar_contratos(request):
    """Vista para administrar contratos pendientes y completados"""
    
    # Verificar que solo administradores puedan acceder
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()):
        messages.error(request, '⛔ Acceso denegado. Solo administradores.')
        return redirect('dashboard')
    
    # Obtener parámetros de filtro
    busqueda = request.GET.get('busqueda', '')
    vendedor_id = request.GET.get('vendedor', '')
    estado = request.GET.get('estado', '')
    
    # Base querysets
    contratos_pendientes = ContratoCliente.objects.filter(
        Q(customer_id__isnull=True) | Q(customer_id='') |
        Q(ods__isnull=True) | Q(ods='')
    ).select_related('cliente_potencial', 'creado_por', 'plan_contratado')
    
    contratos_completados = ContratoCliente.objects.exclude(
        Q(customer_id__isnull=True) | Q(customer_id='') |
        Q(ods__isnull=True) | Q(ods='')
    ).select_related('cliente_potencial', 'creado_por', 'plan_contratado')
    
    # Aplicar filtros a ambos querysets
    if busqueda:
        contratos_pendientes = contratos_pendientes.filter(
            Q(cliente_potencial__nombre__icontains=busqueda) |
            Q(cliente_potencial__apellido__icontains=busqueda) |
            Q(cliente_potencial__cedula__icontains=busqueda) |
            Q(correo_electronico__icontains=busqueda)
        )
        contratos_completados = contratos_completados.filter(
            Q(cliente_potencial__nombre__icontains=busqueda) |
            Q(cliente_potencial__apellido__icontains=busqueda) |
            Q(cliente_potencial__cedula__icontains=busqueda) |
            Q(correo_electronico__icontains=busqueda)
        )
    
    if vendedor_id:
        contratos_pendientes = contratos_pendientes.filter(creado_por_id=vendedor_id)
        contratos_completados = contratos_completados.filter(creado_por_id=vendedor_id)
    
    if estado:
        contratos_pendientes = contratos_pendientes.filter(estado=estado)
        contratos_completados = contratos_completados.filter(estado=estado)
    
    # Ordenar por fecha
    contratos_pendientes = contratos_pendientes.order_by('-fecha_creacion')
    contratos_completados = contratos_completados.order_by('-fecha_creacion')
    
    # Obtener lista de vendedores para el filtro
    from django.contrib.auth.models import User
    vendedores = User.objects.filter(is_active=True, groups__name='Vendedor').order_by('username')
    
    context = {
        'contratos_pendientes': contratos_pendientes,
        'contratos_pendientes_count': contratos_pendientes.count(),
        'contratos_completados': contratos_completados,
        'contratos_completados_count': contratos_completados.count(),
        'vendedores': vendedores,
        'busqueda': busqueda,
        'filtro_vendedor': vendedor_id,
        'filtro_estado': estado,
    }
    
    return render(request, 'Admin/gestionar_contratos.html', context)


# ============================================
# API PARA COMPLETAR CONTRATO
# ============================================
@login_required
def completar_contrato(request, contrato_id):
    """API para completar un contrato (agregar customer_id y ods)"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    # Verificar permisos
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        data = json.loads(request.body)
        customer_id = data.get('customer_id')
        ods = data.get('ods')
        
        if not customer_id or not ods:
            return JsonResponse({'error': 'Customer ID y ODS son requeridos'}, status=400)
        
        contrato = get_object_or_404(ContratoCliente, id=contrato_id)
        contrato.customer_id = customer_id
        contrato.ods = ods
        contrato.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)