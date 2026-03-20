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
    
    return render(request, 'Admin/mapa_usuarios.html', context)



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
    """API para completar un contrato (agregar customer_id, ods, numero_pago_movil y foto_pago)"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    # Verificar permisos
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        contrato = get_object_or_404(ContratoCliente, id=contrato_id)
        
        # Obtener datos del formulario
        customer_id = request.POST.get('customer_id')
        ods = request.POST.get('ods')
        numero_pago_movil = request.POST.get('numero_pago_movil')
        foto_pago = request.FILES.get('foto_pago')
        
        if not customer_id or not ods:
            return JsonResponse({'error': 'Customer ID y ODS son requeridos'}, status=400)
        
        if not numero_pago_movil:
            return JsonResponse({'error': 'Número de pago móvil es requerido'}, status=400)
        
        if not foto_pago:
            return JsonResponse({'error': 'Comprobante de pago es requerido'}, status=400)
        
        # Validar que sea una imagen
        if not foto_pago.content_type.startswith('image/'):
            return JsonResponse({'error': 'El archivo debe ser una imagen'}, status=400)
        
        # Actualizar el contrato
        contrato.customer_id = customer_id
        contrato.ods = ods
        contrato.numero_pago_movil = numero_pago_movil
        contrato.foto_pago = foto_pago
        contrato.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    
@login_required
def editar_contrato(request, contrato_id):
    """Vista para editar un contrato existente (solo administradores)"""
    
    # Verificar permisos (solo admin)
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()):
        messages.error(request, '⛔ Acceso denegado. Solo administradores.')
        return redirect('gestionar_contratos')
    
    contrato = get_object_or_404(
        ContratoCliente.objects.select_related('cliente_potencial'),
        id=contrato_id
    )
    
    if request.method == 'POST':
        form = ContratoClienteForm(request.POST, request.FILES, instance=contrato)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Contrato actualizado exitosamente.')
            return redirect('gestionar_contratos')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Error en {field}: {error}')
    else:
        form = ContratoClienteForm(instance=contrato)
    
    # Verificar que el campo exista antes de modificarlo
    if 'correo_electronico' in form.fields:
        form.fields['correo_electronico'].disabled = True
        form.fields['correo_electronico'].help_text = "El correo no se puede modificar"
    
    # El campo foto_pago ya está incluido en el formulario
    if 'foto_pago' in form.fields:
        form.fields['foto_pago'].required = False
        form.fields['foto_pago'].help_text = "Selecciona una nueva imagen para reemplazar la actual (opcional)"
    
    # Obtener datos para los selects
    planes = Plan.objects.filter(activo=True)
    modalidades = ModalidadEquipo.objects.filter(activo=True)
    viviendas = TipoVivienda.objects.filter(activo=True)
    redes = Red.objects.filter(activo=True)
    
    context = {
        'form': form,
        'contrato': contrato,
        'planes': planes,
        'modalidades': modalidades,
        'viviendas': viviendas,
        'redes': redes,
        'titulo': 'Editar Contrato',
        'subtitulo': f'Modificando contrato de {contrato.cliente_potencial.nombre_completo}',
    }
    
    return render(request, 'Admin/editar_contrato.html', context)



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from .models import Cuadrilla, PerfilUsuario

# ============================================
# VISTA PARA LISTAR CUADRILLAS
# ============================================
@login_required
def lista_cuadrillas(request):
    """Vista para listar todas las cuadrillas"""
    
    # Obtener parámetros de filtro
    busqueda = request.GET.get('busqueda', '')
    estado = request.GET.get('estado', '')
    activo_filtro = request.GET.get('activo', '')
    creador_filtro = request.GET.get('creador', '')
    
    # Query base con prefetch_related para cargar instaladores y sus usuarios
    cuadrillas = Cuadrilla.objects.all().select_related(
        'creado_por'
    ).prefetch_related(
        'instaladores__usuario'  # Esto carga los instaladores y sus usuarios
    )
    
    print(f"DEBUG - Total cuadrillas: {cuadrillas.count()}")
    
    # Mostrar instaladores de cada cuadrilla para debug
    for c in cuadrillas:
        print(f"Cuadrilla {c.nombre}: {c.instaladores.count()} instaladores")
        for i in c.instaladores.all():
            print(f"  - {i.usuario.get_full_name()}")
    
    # Aplicar filtros si existen
    if busqueda:
        cuadrillas = cuadrillas.filter(
            Q(nombre__icontains=busqueda) |
            Q(codigo__icontains=busqueda) |
            Q(instaladores__usuario__first_name__icontains=busqueda) |
            Q(instaladores__usuario__last_name__icontains=busqueda)
        ).distinct()
    
    if estado:
        cuadrillas = cuadrillas.filter(estado=estado)
    
    if activo_filtro == 'activas':
        cuadrillas = cuadrillas.filter(activo=True)
    elif activo_filtro == 'inactivas':
        cuadrillas = cuadrillas.filter(activo=False)
    
    if creador_filtro:
        cuadrillas = cuadrillas.filter(creado_por__username=creador_filtro)
    
    # Calcular estadísticas
    total_cuadrillas = Cuadrilla.objects.all().count()
    disponibles = Cuadrilla.objects.filter(estado='DISPONIBLE', activo=True).count()
    ocupadas = Cuadrilla.objects.filter(estado='OCUPADO', activo=True).count()
    descanso = Cuadrilla.objects.filter(estado='DESCANSO', activo=True).count()
    activas = Cuadrilla.objects.filter(activo=True).count()
    total_instaladores = PerfilUsuario.objects.filter().count()
    
    # Obtener lista de creadores para el filtro
    creadores = User.objects.filter(cuadrillas_creadas__isnull=False).distinct()
    
    # Paginación
    paginator = Paginator(cuadrillas, 10)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    
    # Verificar si es admin
    es_admin = request.user.is_superuser or (hasattr(request.user, 'perfil') and request.user.perfil.rol == 'ADMIN')
    
    context = {
        'page_obj': page_obj,
        'total_cuadrillas': total_cuadrillas,
        'disponibles': disponibles,
        'ocupadas': ocupadas,
        'descanso': descanso,
        'activas': activas,
        'total_instaladores': total_instaladores,
        'estados': Cuadrilla.EstadoCuadrilla.choices,
        'es_admin': es_admin,
        'creadores': creadores,
        'busqueda': busqueda,
        'estado': estado,
        'activo_filtro': activo_filtro,
        'creador_filtro': creador_filtro,
    }
    return render(request, 'Admin/cuadrilla/listar_cuadrillas.html', context)

def es_admin(user):
    """Función helper para verificar si es administrador"""
    return user.is_superuser or (hasattr(user, 'perfil') and user.perfil.rol == 'ADMIN')

@login_required
def crear_cuadrilla(request):
    """Vista para crear una nueva cuadrilla"""
    # Verificar permisos
    if not es_admin(request.user):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('lista_cuadrillas')
    
    # Verificar que el grupo Instalador existe
    try:
        grupo_instalador = Group.objects.get(name='Instalador')
    except Group.DoesNotExist:
        # Crear el grupo si no existe
        grupo_instalador = Group.objects.create(name='Instalador')
        messages.info(request, 'Se creó automáticamente el grupo "Instalador".')
    
    if request.method == 'POST':
        form = CuadrillaForm(request.POST)
        if form.is_valid():
            cuadrilla = form.save(commit=False)
            cuadrilla.creado_por = request.user
            cuadrilla.save()
            form.save_m2m()  # Guardar relaciones ManyToMany
            
            messages.success(request, f'✅ Cuadrilla "{cuadrilla.nombre}" creada exitosamente.')
            return redirect('lista_cuadrillas')
        else:
            messages.error(request, '❌ Por favor corrige los errores en el formulario.')
    else:
        form = CuadrillaForm()
    
    # Obtener instaladores disponibles (los que están en el grupo Instalador)
    instaladores_disponibles = PerfilUsuario.objects.filter(
        usuario__groups=grupo_instalador,
        usuario__is_active=True
    ).select_related('usuario').order_by('usuario__first_name')
    
    context = {
        'form': form,
        'instaladores': instaladores_disponibles,
        'accion': 'Crear',
        'total_instaladores': instaladores_disponibles.count()
    }
    return render(request, 'Admin/cuadrilla/crear_cuadrilla.html', context)



def es_admin(user):
    """Función helper para verificar si es administrador"""
    return user.is_superuser or (hasattr(user, 'perfil') and user.perfil.rol == 'ADMIN')

@login_required
def editar_cuadrilla(request, pk):
    """Vista para editar una cuadrilla existente"""
    # Verificar permisos
    if not es_admin(request.user):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('lista_cuadrillas')
    
    # Obtener la cuadrilla a editar
    cuadrilla = get_object_or_404(Cuadrilla, pk=pk)
    
    # Procesar el formulario
    if request.method == 'POST':
        form = CuadrillaForm(request.POST, instance=cuadrilla)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Cuadrilla "{cuadrilla.nombre}" actualizada exitosamente.')
            return redirect('lista_cuadrillas')
        else:
            messages.error(request, '❌ Por favor corrige los errores en el formulario.')
    else:
        form = CuadrillaForm(instance=cuadrilla)
    
    context = {
        'form': form,
        'cuadrilla': cuadrilla,
        'accion': 'Editar',
    }
    return render(request, 'Admin/cuadrilla/editar_cuadrilla.html', context)

@login_required
def api_detalle_cuadrilla(request, pk):
    """API para obtener detalles de una cuadrilla en formato JSON"""
    try:
        cuadrilla = Cuadrilla.objects.prefetch_related(
            'instaladores__usuario'
        ).get(pk=pk)
        
        data = {
            'id': cuadrilla.id,
            'nombre': cuadrilla.nombre,
            'codigo': cuadrilla.codigo,
            'estado': cuadrilla.estado,
            'estado_display': cuadrilla.get_estado_display(),
            'activo': cuadrilla.activo,
            'fecha_creacion': cuadrilla.fecha_creacion.strftime('%d/%m/%Y'),
            'fecha_actualizacion': cuadrilla.fecha_actualizacion.strftime('%d/%m/%Y %H:%M') if cuadrilla.fecha_actualizacion else None,
            'creado_por': cuadrilla.creado_por.get_full_name() if cuadrilla.creado_por else 'Sistema',
            'instaladores': [
                {
                    'id': inst.id,
                    'nombre': inst.usuario.get_full_name() or inst.usuario.username,
                    'cedula': inst.cedula,
                    'telefono': inst.telefono,
                    'email': inst.usuario.email
                }
                for inst in cuadrilla.instaladores.all()
            ]
        }
        return JsonResponse(data)
    except Cuadrilla.DoesNotExist:
        return JsonResponse({'error': 'Cuadrilla no encontrada'}, status=404)
    
    
@login_required
def cambiar_estado_cuadrilla(request, pk):
    """Vista para cambiar el estado de una cuadrilla"""
    if request.method == 'POST':
        cuadrilla = get_object_or_404(Cuadrilla, pk=pk)
        nuevo_estado = request.POST.get('estado')
        
        # Verificar que el estado sea válido
        estados_validos = [estado[0] for estado in Cuadrilla.EstadoCuadrilla.choices]
        
        if nuevo_estado in estados_validos:
            cuadrilla.estado = nuevo_estado
            cuadrilla.save()
            messages.success(request, f'✅ Estado de "{cuadrilla.nombre}" actualizado a {cuadrilla.get_estado_display()}')
        else:
            messages.error(request, '❌ Estado no válido')
    
    return redirect('lista_cuadrillas')


@login_required
def eliminar_cuadrilla(request, pk):
    """Vista para desactivar (soft delete) una cuadrilla"""
    if request.method == 'POST':
        cuadrilla = get_object_or_404(Cuadrilla, pk=pk)
        
        # Verificar si tiene asignaciones pendientes (opcional)
        # from .models import AsignacionInstalacion
        # asignaciones_pendientes = AsignacionInstalacion.objects.filter(
        #     cuadrilla=cuadrilla,
        #     estado__in=['PENDIENTE', 'ASIGNADO', 'EN_CAMINO', 'EN_PROGRESO']
        # ).exists()
        
        # if asignaciones_pendientes:
        #     messages.error(request, f'❌ No se puede desactivar "{cuadrilla.nombre}" porque tiene asignaciones pendientes.')
        # else:
        # Soft delete - desactivar en lugar de eliminar
        cuadrilla.activo = False
        cuadrilla.estado = Cuadrilla.EstadoCuadrilla.INACTIVO
        cuadrilla.save()
        messages.success(request, f'✅ Cuadrilla "{cuadrilla.nombre}" desactivada exitosamente.')
        
        return redirect('lista_cuadrillas')
    
    # Si alguien intenta acceder por GET, redirigir
    return redirect('lista_cuadrillas')    