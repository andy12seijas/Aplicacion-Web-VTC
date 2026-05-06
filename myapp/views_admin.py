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
    supervisor_group = Group.objects.get(name='Supervisor')  # 👈 NUEVO
    
    total_administradores = admin_group.user_set.count()
    total_vendedores = vendedor_group.user_set.count()
    total_instaladores = instalador_group.user_set.count()
    total_supervisores = supervisor_group.user_set.count()  # 👈 NUEVO
    total_superusuarios = User.objects.filter(is_superuser=True).count()
    
    paginator = Paginator(usuarios, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_usuarios': total_usuarios,
        'usuarios_activos': usuarios_activos,
        'total_administradores': total_administradores,
        'total_vendedores': total_vendedores,
        'total_instaladores': total_instaladores,
        'total_supervisores': total_supervisores,  # 👈 NUEVO
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
@permission_required('auth.change_user', raise_exception=True)
def cambiar_estado_usuario(request, user_id):
    """Activar/Desactivar usuario (User y PerfilUsuario)"""
    if request.method == 'POST':
        usuario = get_object_or_404(User, id=user_id)
        
        # No permitir desactivar al propio usuario
        if usuario == request.user:
            messages.error(request, '❌ No puedes desactivar tu propia cuenta.')
            return redirect('lista_usuarios')
        
        # Cambiar estado del User
        usuario.is_active = not usuario.is_active
        usuario.save()
        
        # Cambiar estado del PerfilUsuario
        if hasattr(usuario, 'perfil'):
            perfil = usuario.perfil
            perfil.activo = not perfil.activo
            perfil.save()
        
        estado = "activado" if usuario.is_active else "desactivado"
        messages.success(request, f'✅ Usuario "{usuario.username}" {estado} exitosamente.')
    
    return redirect('lista_usuarios')

def logout_view(request):
    """Cierra la sesión del usuario"""
    logout(request)
    messages.success(request, 'Sesión cerrada exitosamente.')
    return redirect('login')

@login_required
def mapa_usuarios(request):
    """Vista para administradores - Mapa con CUADRILLAS y VENDEDORES"""
    
    # Verificar permisos
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists() or request.user.groups.filter(name='Supervisor').exists()):
        messages.error(request, '⛔ Acceso denegado. Solo administradores.')
        return redirect('lista_clientes')
    
    # Obtener filtros de la URL
    tipo_usuario = request.GET.get('tipo', 'todos')
    buscar = request.GET.get('buscar', '')
    hoy = timezone.now().date()
    
    # ============================================
    # 1. DATOS DE CUADRILLAS
    # ============================================
    cuadrillas = Cuadrilla.objects.filter(activo=True).prefetch_related('instaladores__usuario')
    
    if buscar:
        cuadrillas = cuadrillas.filter(
            Q(nombre__icontains=buscar) |
            Q(codigo__icontains=buscar) |
            Q(instaladores__usuario__first_name__icontains=buscar) |
            Q(instaladores__usuario__last_name__icontains=buscar)
        ).distinct()
    
    datos_cuadrillas = []
    for cuadrilla in cuadrillas:
        ubicaciones_instaladores = []
        instaladores_data = []
        
        for instalador in cuadrilla.instaladores.all():
            # Obtener estado individual del instalador
            instalador_ocupado = False
            instalador_tarea = "Sin asignación"
            instalador_pendientes = 0
            
            # Verificar si el instalador tiene asignaciones activas
            asignaciones_instalador = AsignacionContrato.objects.filter(
                cuadrilla=cuadrilla,
                activo=True
            )
            
            # Contar instalaciones pendientes de la cuadrilla (para el instalador)
            instalador_pendientes = asignaciones_instalador.exclude(
                instalacion__completada=True
            ).count()
            
            # Verificar si el instalador está ocupado (tiene alguna tarea activa)
            if instalador_pendientes > 0:
                instalador_ocupado = True
                # Verificar si es instalación o soporte
                instalacion_activa = Instalacion.objects.filter(
                    asignacion__in=asignaciones_instalador,
                    completada=False
                ).first()
                if instalacion_activa:
                    instalador_tarea = "Instalación"
                else:
                    soporte_activo = Soporte.objects.filter(
                        asignacion__in=asignaciones_instalador, 
                        estado__in=['PENDIENTE', 'EN_PROCESO']
                    ).first()
                    if soporte_activo:
                        instalador_tarea = f"Soporte: {soporte_activo.get_tipo_display()}"
            
            try:
                ubicacion = UbicacionUsuario.objects.get(usuario=instalador.usuario)
                ubicaciones_instaladores.append({
                    'lat': ubicacion.latitud,
                    'lng': ubicacion.longitud,
                    'ultima_actualizacion': ubicacion.ultima_actualizacion,
                    'activo': ubicacion.esta_activo,
                })
                instaladores_data.append({
                    'id': instalador.id,
                    'nombre': instalador.usuario.get_full_name() or instalador.usuario.username,
                    'cedula': instalador.cedula,
                    'telefono': instalador.telefono,
                    'activo': ubicacion.esta_activo,
                    'ultima_actualizacion': ubicacion.ultima_actualizacion.strftime('%H:%M %d/%m/%Y'),
                    'ocupado': instalador_ocupado,
                    'tarea_actual': instalador_tarea,
                    'instalaciones_pendientes': instalador_pendientes,
                })
            except UbicacionUsuario.DoesNotExist:
                instaladores_data.append({
                    'id': instalador.id,
                    'nombre': instalador.usuario.get_full_name() or instalador.usuario.username,
                    'cedula': instalador.cedula,
                    'telefono': instalador.telefono,
                    'activo': False,
                    'ultima_actualizacion': 'Sin ubicación',
                    'ocupado': instalador_ocupado,
                    'tarea_actual': instalador_tarea,
                    'instalaciones_pendientes': instalador_pendientes,
                })
        
        if ubicaciones_instaladores:
            lat_promedio = sum(u['lat'] for u in ubicaciones_instaladores) / len(ubicaciones_instaladores)
            lng_promedio = sum(u['lng'] for u in ubicaciones_instaladores) / len(ubicaciones_instaladores)
            hace_1hora = timezone.now() - timedelta(hours=1)
            activos = any(u['ultima_actualizacion'] > hace_1hora for u in ubicaciones_instaladores)
            ultima_actualizacion = max(u['ultima_actualizacion'] for u in ubicaciones_instaladores)
            
            # Contar instalaciones pendientes de la cuadrilla
            instalaciones_pendientes = AsignacionContrato.objects.filter(
                cuadrilla=cuadrilla,
                activo=True
            ).exclude(
                instalacion__completada=True
            ).count()
            
            # Determinar color según estado
            color_estado = '#FF6B00'
            if cuadrilla.estado == 'DISPONIBLE':
                color_estado = '#4CAF50'
            elif cuadrilla.estado == 'OCUPADO':
                color_estado = '#FF9800'
            elif cuadrilla.estado == 'DESCANSO':
                color_estado = '#2196F3'
            elif cuadrilla.estado == 'INACTIVO':
                color_estado = '#9E9E9E'
            
            datos_cuadrillas.append({
                'tipo': 'cuadrilla',
                'cuadrilla': {
                    'id': cuadrilla.id,
                    'nombre': cuadrilla.nombre,
                    'codigo': cuadrilla.codigo,
                    'estado': cuadrilla.estado,
                    'estado_display': cuadrilla.get_estado_display(),
                    'instaladores': instaladores_data,
                    'instalaciones_pendientes': instalaciones_pendientes,
                },
                'latitud': lat_promedio,
                'longitud': lng_promedio,
                'ultima_actualizacion': ultima_actualizacion.isoformat() if hasattr(ultima_actualizacion, 'isoformat') else str(ultima_actualizacion),
                'activo': activos,
                'color': color_estado,
                'icono': '👥',
                'radius': 14,
            })
    
    # ============================================
    # 2. DATOS DE VENDEDORES
    # ============================================
    vendedores = User.objects.filter(groups__name='Vendedor', is_active=True)
    
    if buscar:
        vendedores = vendedores.filter(
            Q(username__icontains=buscar) |
            Q(first_name__icontains=buscar) |
            Q(last_name__icontains=buscar)
        )
    
    datos_vendedores = []
    for vendedor in vendedores:
        try:
            ubicacion = UbicacionUsuario.objects.get(usuario=vendedor)
            
            total_clientes = ClientePotencial.objects.filter(creado_por=vendedor).count()
            clientes_hoy = ClientePotencial.objects.filter(creado_por=vendedor, fecha_registro=hoy).count()
            contratos_proceso = ContratoCliente.objects.filter(creado_por=vendedor, estado='EN_PROCESO').count()
            contratos_completados = ContratoCliente.objects.filter(creado_por=vendedor, estado='COMPLETADO').count()
            
            datos_vendedores.append({
                'tipo': 'vendedor',
                'vendedor': {
                    'id': vendedor.id,
                    'username': vendedor.username,
                    'first_name': vendedor.first_name,
                    'last_name': vendedor.last_name,
                    'telefono': getattr(vendedor.perfil, 'telefono', 'No registrado') if hasattr(vendedor, 'perfil') else 'No registrado',
                    'total_clientes': total_clientes,
                    'total_clientes_hoy': clientes_hoy,
                    'total_contratos_proceso': contratos_proceso,
                    'total_contratos_completados': contratos_completados,
                },
                'latitud': ubicacion.latitud,
                'longitud': ubicacion.longitud,
                'ultima_actualizacion': ubicacion.ultima_actualizacion.isoformat(),
                'activo': ubicacion.esta_activo,
                'color': '#2196F3',
                'icono': '👤',
                'radius': 10,
            })
        except UbicacionUsuario.DoesNotExist:
            pass
    
    # ============================================
    # 3. COMBINAR Y FILTRAR DATOS
    # ============================================
    datos_mapa = datos_cuadrillas + datos_vendedores
    
    if tipo_usuario == 'cuadrillas':
        datos_mapa = [d for d in datos_mapa if d['tipo'] == 'cuadrilla']
    elif tipo_usuario == 'vendedores':
        datos_mapa = [d for d in datos_mapa if d['tipo'] == 'vendedor']
    
    datos_mapa_con_ubicacion = [d for d in datos_mapa if d.get('latitud') and d.get('longitud')]
    
    hace_1hora = timezone.now() - timedelta(hours=1)
    activos_ahora = sum(1 for d in datos_mapa_con_ubicacion if d.get('activo', False))
    
    stats_por_tipo = [
        {'nombre': 'Cuadrillas', 'cantidad': len([d for d in datos_mapa if d['tipo'] == 'cuadrilla'])},
        {'nombre': 'Vendedores', 'cantidad': len([d for d in datos_mapa if d['tipo'] == 'vendedor'])},
    ]
    
    context = {
        'ubicaciones': datos_mapa_con_ubicacion,
        'total_usuarios': len(datos_mapa),
        'activos_ahora': activos_ahora,
        'stats_por_tipo': stats_por_tipo,
        'filtro_tipo': tipo_usuario,
        'buscar': buscar,
    }
    
    return render(request, 'Admin/mapa_usuarios.html', context)

@login_required
def panel_administrativo(request):
    """Vista del panel administrativo con botones de acceso rápido según el rol"""
    
    from django.contrib.auth.models import User, Group
    
    # Obtener el rol del usuario actual
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_supervisor = request.user.groups.filter(name='Supervisor').exists()
    
    # Si no es admin ni supervisor, redirigir
    if not (es_admin or es_supervisor):
        messages.error(request, '⛔ Acceso denegado. No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Estadísticas para mostrar (comunes)
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
    
    try:
        total_supervisores = Group.objects.get(name='Supervisor').user_set.filter(is_active=True).count()
    except Group.DoesNotExist:
        total_supervisores = 0
    
    # Variables para controlar qué botones mostrar
    mostrar_todos = es_admin  # Los administradores ven todo
    es_supervisor_role = es_supervisor  # Los supervisores ven solo lo permitido
    
    context = {
        'total_usuarios': total_usuarios,
        'total_vendedores': total_vendedores,
        'total_instaladores': total_instaladores,
        'total_administradores': total_administradores,
        'total_supervisores': total_supervisores,
        'mostrar_todos': mostrar_todos,
        'es_supervisor': es_supervisor_role,
    }
    
    return render(request, 'Admin/panel_administrativo.html', context)


@login_required
def gestionar_contratos(request):
    """Vista para administrar contratos pendientes y completados"""
    
    # Verificar que solo administradores y supervisores puedan acceder
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_supervisor = request.user.groups.filter(name='Supervisor').exists()
    
    if not (es_admin or es_supervisor):
        messages.error(request, '⛔ Acceso denegado. No tienes permisos.')
        return redirect('dashboard')
    
    # Obtener parámetros de filtro
    busqueda = request.GET.get('busqueda', '')
    vendedor_id = request.GET.get('vendedor', '')
    estado = request.GET.get('estado', '')
    tab_activa = request.GET.get('tab', 'pendientes')
    
    # ========== CONTRATOS PENDIENTES (EXCLUYE NO_COMPLETADO) ==========
    contratos_pendientes = ContratoCliente.objects.filter(
        Q(customer_id__isnull=True) | Q(customer_id='') |
        Q(ods__isnull=True) | Q(ods='')
    ).exclude(estado='NO_COMPLETADO').select_related('cliente_potencial', 'creado_por', 'plan_contratado')
    
    # ========== CONTRATOS COMPLETADOS (EXCLUYE NO_COMPLETADO) ==========
    contratos_completados = ContratoCliente.objects.exclude(
        Q(customer_id__isnull=True) | Q(customer_id='') |
        Q(ods__isnull=True) | Q(ods='')
    ).exclude(estado='NO_COMPLETADO').select_related('cliente_potencial', 'creado_por', 'plan_contratado')
    
    # ========== CONTRATOS NO COMPLETADOS (SOLO PARA FILTRO) ==========
    contratos_no_completados = ContratoCliente.objects.filter(estado='NO_COMPLETADO').select_related('cliente_potencial', 'creado_por', 'plan_contratado')
    contratos_no_completados_count = contratos_no_completados.count()
    
    # ========== APLICAR FILTROS ==========
    # Contenedor para el queryset según el estado seleccionado
    if estado == 'NO_COMPLETADO':
        # Si el filtro es "No Completado", mostrar solo esos
        contratos_activos = contratos_no_completados
    else:
        # Si no, usar los querysets normales según la pestaña
        if tab_activa == 'pendientes':
            contratos_activos = contratos_pendientes
        else:
            contratos_activos = contratos_completados
    
    # Aplicar búsqueda
    if busqueda and estado != 'NO_COMPLETADO':
        # Búsqueda normal
        contratos_pendientes = contratos_pendientes.filter(
            Q(cliente_potencial__nombre__icontains=busqueda) |
            Q(cliente_potencial__apellido__icontains=busqueda) |
            Q(cliente_potencial__cedula__icontains=busqueda) |
            Q(correo_electronico__icontains=busqueda) |
            Q(customer_id__icontains=busqueda) |
            Q(ods__icontains=busqueda) |
            Q(direccion_detallada__icontains=busqueda)
        )
        contratos_completados = contratos_completados.filter(
            Q(cliente_potencial__nombre__icontains=busqueda) |
            Q(cliente_potencial__apellido__icontains=busqueda) |
            Q(cliente_potencial__cedula__icontains=busqueda) |
            Q(correo_electronico__icontains=busqueda) |
            Q(customer_id__icontains=busqueda) |
            Q(ods__icontains=busqueda) |
            Q(direccion_detallada__icontains=busqueda)
        )
        contratos_no_completados = contratos_no_completados.filter(
            Q(cliente_potencial__nombre__icontains=busqueda) |
            Q(cliente_potencial__apellido__icontains=busqueda) |
            Q(cliente_potencial__cedula__icontains=busqueda) |
            Q(correo_electronico__icontains=busqueda) |
            Q(customer_id__icontains=busqueda) |
            Q(ods__icontains=busqueda) |
            Q(direccion_detallada__icontains=busqueda)
        )
    elif busqueda and estado == 'NO_COMPLETADO':
        contratos_no_completados = contratos_no_completados.filter(
            Q(cliente_potencial__nombre__icontains=busqueda) |
            Q(cliente_potencial__apellido__icontains=busqueda) |
            Q(cliente_potencial__cedula__icontains=busqueda) |
            Q(correo_electronico__icontains=busqueda) |
            Q(customer_id__icontains=busqueda) |
            Q(ods__icontains=busqueda) |
            Q(direccion_detallada__icontains=busqueda)
        )
    
    # Aplicar filtro por vendedor
    if vendedor_id and estado != 'NO_COMPLETADO':
        contratos_pendientes = contratos_pendientes.filter(creado_por_id=vendedor_id)
        contratos_completados = contratos_completados.filter(creado_por_id=vendedor_id)
    elif vendedor_id and estado == 'NO_COMPLETADO':
        contratos_no_completados = contratos_no_completados.filter(creado_por_id=vendedor_id)
    
    # Ordenar
    contratos_pendientes = contratos_pendientes.order_by('-fecha_creacion')
    contratos_completados = contratos_completados.order_by('-fecha_creacion')
    contratos_no_completados = contratos_no_completados.order_by('-fecha_creacion')
    
    # ===== PAGINACIÓN =====
    from django.core.paginator import Paginator
    
    # Si el filtro es NO_COMPLETADO, mostrar en la pestaña pendientes
    if estado == 'NO_COMPLETADO':
        paginator_pendientes = Paginator(contratos_no_completados, 10)
        page_pendientes = request.GET.get('page_pendientes', 1)
        contratos_pendientes_page = paginator_pendientes.get_page(page_pendientes)
        contratos_completados_page = []  # Vacío porque mostramos solo una tabla
        # Forzar tab_activa a pendientes para mostrar la tabla
        tab_activa = 'pendientes'
    else:
        # Paginación normal
        paginator_pendientes = Paginator(contratos_pendientes, 10)
        page_pendientes = request.GET.get('page_pendientes', 1)
        contratos_pendientes_page = paginator_pendientes.get_page(page_pendientes)
        
        paginator_completados = Paginator(contratos_completados, 10)
        page_completados = request.GET.get('page_completados', 1)
        contratos_completados_page = paginator_completados.get_page(page_completados)
    
    # Obtener lista de vendedores
    from django.contrib.auth.models import User
    vendedores = User.objects.filter(is_active=True, groups__name='Vendedor').order_by('username')
    
    context = {
        'contratos_pendientes': contratos_pendientes_page,
        'contratos_pendientes_count': contratos_pendientes.count(),
        'contratos_completados': contratos_completados_page if estado != 'NO_COMPLETADO' else [],
        'contratos_completados_count': contratos_completados.count(),
        'contratos_no_completados_count': contratos_no_completados_count,
        'contratos_no_completados': contratos_no_completados if estado == 'NO_COMPLETADO' else [],
        'vendedores': vendedores,
        'busqueda': busqueda,
        'filtro_vendedor': vendedor_id,
        'filtro_estado': estado,
        'tab_activa': tab_activa,
        'es_admin': es_admin,
        'es_supervisor': es_supervisor,
        'mostrando_no_completados': estado == 'NO_COMPLETADO',
    }
    
    return render(request, 'Admin/gestionar_contratos.html', context)


@login_required
def reactivar_contrato(request, contrato_id):
    """
    Reactivar un contrato que estaba en estado NO_COMPLETADO a EN_PROCESO
    Solo accesible para Administradores y Supervisores
    """
    import json
    
    # Verificar permisos (solo administradores y supervisores)
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_supervisor = request.user.groups.filter(name='Supervisor').exists()
    
    if not (es_admin or es_supervisor):
        return JsonResponse({
            'success': False, 
            'error': 'No tienes permisos para realizar esta acción'
        }, status=403)
    
    if request.method != 'POST':
        return JsonResponse({
            'success': False, 
            'error': 'Método no permitido'
        }, status=405)
    
    try:
        contrato = ContratoCliente.objects.get(id=contrato_id)
        
        # Verificar que el contrato esté en estado NO_COMPLETADO
        if contrato.estado != 'NO_COMPLETADO':
            return JsonResponse({
                'success': False, 
                'error': f'El contrato está en estado "{contrato.estado}", no en "No Completado"'
            })
        
        # Cambiar estado a EN_PROCESO
        contrato.estado = 'EN_PROCESO'
        contrato.save()
        
        # Respuesta exitosa
        return JsonResponse({
            'success': True, 
            'message': f'Contrato reactivado correctamente. Ahora está en estado "En Proceso".'
        })
        
    except ContratoCliente.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': 'Contrato no encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Error al reactivar: {str(e)}'
        }, status=500)


@login_required
def marcar_contrato_no_completado(request, contrato_id):
    """Vista para marcar un contrato como 'No Completado'"""
    
    # Verificar permisos
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_supervisor = request.user.groups.filter(name='Supervisor').exists()
    
    if not (es_admin or es_supervisor):
        return JsonResponse({'error': 'No tienes permisos para realizar esta acción'}, status=403)
    
    contrato = get_object_or_404(ContratoCliente, id=contrato_id)
    
    if request.method == 'POST':
        contrato.estado = 'NO_COMPLETADO'
        contrato.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Contrato #{contrato.id} marcado como No Completado'
        })
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


# ============================================
# API PARA COMPLETAR CONTRATO
# ============================================
@login_required
def completar_contrato(request, contrato_id):
    """API para completar un contrato (agregar customer_id, ods, numero_pago_movil y foto_pago)"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    # Verificar permisos
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists() or request.user.groups.filter(name='Supervisor').exists()):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        contrato = get_object_or_404(ContratoCliente, id=contrato_id)
        
        # Obtener datos del formulario
        customer_id = request.POST.get('customer_id')
        ods = request.POST.get('ods')
       
        
        if not customer_id or not ods:
            return JsonResponse({'error': 'Customer ID y ODS son requeridos'}, status=400)
        
        if customer_id and ods:
            # Verificar si ya existen en otros contratos
            if ContratoCliente.objects.filter(customer_id=customer_id).exclude(id=contrato_id).exists():
                return JsonResponse({'error': 'Este Customer ID ya está asignado a otro contrato'}, status=400)
            
            if ContratoCliente.objects.filter(ods=ods).exclude(id=contrato_id).exists():
                return JsonResponse({'error': 'Esta ODS ya está asignada a otro contrato'}, status=400)
        
       
        
        # Validar que sea una imagen
        
        
        # Actualizar el contrato
        contrato.customer_id = customer_id
        contrato.ods = ods
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
    paginator = Paginator(cuadrillas, 5)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    
    # Verificar si es admin
    es_admin = request.user.is_superuser 
    
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
    
    # Obtener instaladores disponibles para mostrar en el template (con toda la información)
    instaladores_disponibles = PerfilUsuario.objects.filter(
        usuario__groups=grupo_instalador,
        usuario__is_active=True
    ).exclude(
        cuadrillas__isnull=False  # Excluir los que ya están en alguna cuadrilla
    ).select_related('usuario').order_by('usuario__first_name')
    
    # Crear una lista con los datos formateados para el template
    instaladores_data = []
    for inst in instaladores_disponibles:
        instaladores_data.append({
            'id': inst.id,
            'nombre': inst.usuario.get_full_name() or inst.usuario.username,
            'cedula': inst.cedula or 'Sin cédula',
            'telefono': inst.telefono or 'Sin teléfono',
        })
    
    context = {
        'form': form,
        'instaladores': instaladores_disponibles,
        'instaladores_data': instaladores_data,
        'accion': 'Crear',
        'total_instaladores': instaladores_disponibles.count()
    }
    return render(request, 'Admin/cuadrilla/crear_cuadrilla.html', context)



def es_admin(user):
    """Función helper para verificar si es administrador"""
    return user.is_superuser 
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