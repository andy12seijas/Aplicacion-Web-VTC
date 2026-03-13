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
    """Vista para administradores - Mapa con ubicación ACTUAL de usuarios (vendedores, instaladores, etc)"""
    
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
    if tipo_usuario != 'todos':
        ubicaciones = ubicaciones.filter(usuario__groups__name=tipo_usuario)
    
    # Filtrar por búsqueda
    if buscar:
        ubicaciones = ubicaciones.filter(
            Q(usuario__username__icontains=buscar) |
            Q(usuario__first_name__icontains=buscar) |
            Q(usuario__last_name__icontains=buscar) |
            Q(contenido_asociado__icontains=buscar)
        )
    
    # Preparar datos para el mapa
    datos_mapa = []
    for ubicacion in ubicaciones:
        # Obtener el grupo del usuario (vendedor, instalador, etc)
        grupo = ubicacion.usuario.groups.first()
        tipo = grupo.name if grupo else 'Sin grupo'
        
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