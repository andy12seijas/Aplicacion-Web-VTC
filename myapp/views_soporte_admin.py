from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from datetime import datetime
from django.utils import timezone

from myapp.views_admin import es_admin

from .models import Instalacion, Soporte, ModeloModem, User, Cuadrilla


def es_instalador_o_admin(user):
    """Verifica si el usuario es instalador o administrador"""
    return user.is_authenticated and (
        user.is_superuser or 
        user.groups.filter(name='Administrador').exists() or 
        user.groups.filter(name='Instalador').exists()
    )


from django.db.models import Prefetch

@login_required
@user_passes_test(es_admin)
def lista_soportes_admin(request):
    """Vista de lista de soportes para administradores"""
    
    # Obtener parámetros de filtro
    busqueda = request.GET.get('busqueda', '').strip()
    tipo_seleccionado = request.GET.get('tipo', '')
    instalador_seleccionado = request.GET.get('instalador', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    tab_activa = request.GET.get('tab', 'pendientes')
    
    # Base de consulta - TODOS los soportes
    soportes = Soporte.objects.all().select_related(
        'instalacion',
        'instalacion__asignacion',
        'instalacion__asignacion__contrato__cliente_potencial',
        'instalacion__asignacion__venta_directa',
        'cuadrilla'
    ).prefetch_related(
        'instaladores'
    ).order_by('-fecha_hora_servicio')
    
    # ========== APLICAR FILTROS (igual que en instalaciones_pendientes) ==========
    
    if busqueda:
        soportes = soportes.filter(
            # Buscar en los campos de la instalación relacionada
            Q(instalacion__asignacion__contrato__cliente_potencial__nombre__icontains=busqueda) |
            Q(instalacion__asignacion__contrato__cliente_potencial__apellido__icontains=busqueda) |
            Q(instalacion__asignacion__contrato__cliente_potencial__cedula__icontains=busqueda) |
            Q(instalacion__asignacion__contrato__customer_id__icontains=busqueda) |
            Q(instalacion__asignacion__contrato__ods__icontains=busqueda) |
            Q(instalacion__asignacion__venta_directa__nombre__icontains=busqueda) |
            Q(instalacion__asignacion__venta_directa__apellido__icontains=busqueda) |
            Q(instalacion__asignacion__venta_directa__cedula__icontains=busqueda) |
            Q(instalacion__asignacion__venta_directa__customer_id__icontains=busqueda) |
            Q(instalacion__asignacion__venta_directa__nro_orden__icontains=busqueda)
        )
    
    if tipo_seleccionado:
        soportes = soportes.filter(tipo=tipo_seleccionado)
    
    if instalador_seleccionado:
        soportes = soportes.filter(instaladores__id=instalador_seleccionado)
    
    if fecha_desde:
        try:
            soportes = soportes.filter(fecha_hora_servicio__date__gte=fecha_desde)
        except:
            pass
    
    if fecha_hasta:
        try:
            soportes = soportes.filter(fecha_hora_servicio__date__lte=fecha_hasta)
        except:
            pass
    
    # Separar por estado
    soportes_pendientes = soportes.filter(
        estado__in=['PENDIENTE', 'EN_PROCESO']
    )
    
    soportes_completados = soportes.filter(
        estado='COMPLETADO'
    )
    
    # Paginación
    paginator_pendientes = Paginator(soportes_pendientes, 15)
    page_pendientes = request.GET.get('page_pendientes', 1)
    soportes_pendientes_page = paginator_pendientes.get_page(page_pendientes)
    
    paginator_completados = Paginator(soportes_completados, 15)
    page_completados = request.GET.get('page_completados', 1)
    soportes_completados_page = paginator_completados.get_page(page_completados)
    
    # Obtener instaladores para el filtro
    instaladores = User.objects.filter(
        Q(groups__name='Instalador') | Q(groups__name='Administrador')
    ).distinct().order_by('first_name', 'username')
    
    context = {
        'soportes_pendientes': soportes_pendientes_page,
        'soportes_completados': soportes_completados_page,
        'total_pendientes': soportes_pendientes.count(),
        'total_completados': soportes_completados.count(),
        'busqueda': busqueda,
        'tipo_seleccionado': tipo_seleccionado,
        'instalador_seleccionado': instalador_seleccionado,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'tab_activa': tab_activa,
        'instaladores': instaladores,
        'es_admin': True,
    }
    
    return render(request, 'Admin/soporte_admin.html', context)


@login_required
@user_passes_test(es_instalador_o_admin)
@require_http_methods(["GET"])
def detalle_soporte_admin(request, soporte_id):
    """Retorna los detalles de un soporte en formato JSON para el modal"""
    
    soporte = get_object_or_404(Soporte, id=soporte_id)
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    # Verificar permisos
    if not es_admin and request.user not in soporte.instaladores.all():
        return JsonResponse({'error': 'No tienes permiso para ver este soporte'}, status=403)
    
    # Obtener lista de instaladores
    instaladores_lista = []
    for inst in soporte.instaladores.all():
        nombre = inst.get_full_name() if inst.get_full_name() else inst.username
        instaladores_lista.append(nombre)
    
    # Construir respuesta completa
    data = {
        'id': soporte.id,
        'tipo': soporte.tipo,
        'tipo_display': soporte.get_tipo_display(),
        'estado': soporte.estado,
        'estado_display': soporte.get_estado_display(),
        'fecha_hora_servicio': soporte.fecha_hora_servicio.strftime('%d/%m/%Y %H:%M') if soporte.fecha_hora_servicio else 'No registrada',
        'fecha_creacion': soporte.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        'fecha_actualizacion': soporte.fecha_actualizacion.strftime('%d/%m/%Y %H:%M'),
        
        # Información del cliente
        'cliente_nombre': soporte.nombre_cliente,
        'cliente_cedula': soporte.cedula_cliente,
        'direccion': soporte.direccion,
        'customer_id': soporte.customer_id or 'N/A',
        'plan': soporte.plan or 'N/A',
        'atr': soporte.atr or 'N/A',
        
        # Información de la instalación original
        'instalacion_id': soporte.instalacion.id,
        'modelo_modem_original': soporte.instalacion.modelo_modem.nombre if soporte.instalacion.modelo_modem else 'N/A',
        'sn_modem_original': soporte.instalacion.sn_modem or 'N/A',
        
        # Datos del soporte
        'falla_encontrada': soporte.falla_encontrada,
        'solucion': soporte.solucion,
        'observaciones': soporte.observaciones or '',
        
        # Datos del nuevo módem (si aplica)
        'modelo_modem': soporte.modelo_modem.nombre if soporte.modelo_modem else 'No se cambió',
        'sn_modem': soporte.sn_modem or 'No se cambió',
        'mac_modem': soporte.mac_modem or 'No se cambió',
        
        # Materiales
        'inicio_fibra': soporte.inicio_fibra or 0,
        'final_fibra': soporte.final_fibra or 0,
        'metros_utilizados': soporte.metros_utilizados,
        'conectores': soporte.conectores or 0,
        'rosetas': soporte.rosetas or 0,
        'patch_cord': soporte.patch_cord or 0,
        'tensores': soporte.tensores or 0,
        'conectores_malos': soporte.conectores_malos or 0,
        
        # Datos NAP
        'caja_nap_utilizada': soporte.caja_nap_utilizada or 'N/A',
        'puerto_nap_utilizado': soporte.puerto_nap_utilizado or 'N/A',
        
        # Ubicación
        'pin_ubicacion_lat': soporte.pin_ubicacion_lat,
        'pin_ubicacion_lng': soporte.pin_ubicacion_lng,
        'pin_ubicacion_url': f"https://www.google.com/maps?q={soporte.pin_ubicacion_lat},{soporte.pin_ubicacion_lng}" if soporte.pin_ubicacion_lat and soporte.pin_ubicacion_lng else None,
        
        # Fotos
        'fotos': soporte.fotos or [],
        
        # Instaladores
        'instaladores': instaladores_lista,
        
        # Cuadrilla
        'cuadrilla': soporte.cuadrilla.nombre if soporte.cuadrilla else 'No asignada',
        
        # Permisos
        'puede_editar': soporte.estado not in ['COMPLETADO', 'CANCELADO'],
        'es_admin': es_admin,
    }
    
    return JsonResponse(data)


@login_required
@user_passes_test(es_instalador_o_admin)
@require_http_methods(["POST"])
def cambiar_estado_admin(request, soporte_id):
    """Cambia el estado de un soporte (solo administradores)"""
    
    soporte = get_object_or_404(Soporte, id=soporte_id)
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    # Solo administradores pueden cambiar el estado
    if not es_admin:
        return JsonResponse({'error': 'No tienes permiso para cambiar el estado'}, status=403)
    
    try:
        import json
        data = json.loads(request.body)
        nuevo_estado = data.get('estado')
        
        # Validar que el estado sea válido
        estados_validos = ['PENDIENTE', 'EN_PROCESO', 'COMPLETADO', 'INCOMPLETO', 'CANCELADO']
        if nuevo_estado not in estados_validos:
            return JsonResponse({'error': 'Estado no válido'}, status=400)
        
        # Cambiar el estado
        soporte.estado = nuevo_estado
        soporte.save()
        
        return JsonResponse({
            'success': True,
            'mensaje': f'Estado actualizado a {soporte.get_estado_display()}',
            'nuevo_estado': nuevo_estado,
            'nuevo_estado_display': soporte.get_estado_display()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Datos inválidos'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    
    
@login_required
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Administrador').exists())
def historial_soportes_instalacion(request, instalacion_id):
    """Vista para ver el historial de soportes de una instalación específica"""
    
    # Obtener la instalación
    instalacion = get_object_or_404(Instalacion, id=instalacion_id)
    
    # Obtener todos los soportes de esta instalación
    soportes = Soporte.objects.filter(instalacion=instalacion).order_by('-fecha_hora_servicio')
    
    # Obtener parámetros de filtro
    busqueda = request.GET.get('busqueda', '')
    tipo_seleccionado = request.GET.get('tipo', '')
    estado_seleccionado = request.GET.get('estado', '')
    
    # Aplicar filtros
    if busqueda:
        soportes = soportes.filter(
            Q(falla_encontrada__icontains=busqueda) |
            Q(solucion__icontains=busqueda) |
            Q(instaladores__username__icontains=busqueda) |
            Q(instaladores__first_name__icontains=busqueda) |
            Q(instaladores__last_name__icontains=busqueda)
        )
    
    if tipo_seleccionado:
        soportes = soportes.filter(tipo=tipo_seleccionado)
    
    if estado_seleccionado:
        soportes = soportes.filter(estado=estado_seleccionado)
    
    # Paginación
    paginator = Paginator(soportes, 10)
    page_number = request.GET.get('page', 1)
    soportes_page = paginator.get_page(page_number)
    
    # Estadísticas
    total_soportes = soportes.count()
    soportes_pendientes = soportes.filter(estado__in=['PENDIENTE', 'EN_PROCESO']).count()
    soportes_completados = soportes.filter(estado='COMPLETADO').count()
    
    context = {
        'instalacion': instalacion,
        'soportes': soportes_page,
        'total_soportes': total_soportes,
        'soportes_pendientes': soportes_pendientes,
        'soportes_completados': soportes_completados,
        'busqueda': busqueda,
        'tipo_seleccionado': tipo_seleccionado,
        'estado_seleccionado': estado_seleccionado,
        'tipos_soporte': Soporte.TipoSoporte.choices,
        'estados_soporte': Soporte.EstadoSoporte.choices,
    }
    
    return render(request, 'Admin/historial_soportes_instalacion.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Administrador').exists())
def detalle_soporte_modal(request, soporte_id):
    """Retorna los detalles de un soporte en formato JSON para el modal"""
    
    soporte = get_object_or_404(Soporte, id=soporte_id)
    
    # Obtener lista de instaladores
    instaladores_lista = []
    for inst in soporte.instaladores.all():
        nombre = inst.get_full_name() if inst.get_full_name() else inst.username
        instaladores_lista.append(nombre)
    
    data = {
        'id': soporte.id,
        'tipo': soporte.tipo,
        'tipo_display': soporte.get_tipo_display(),
        'estado': soporte.estado,
        'estado_display': soporte.get_estado_display(),
        'fecha_hora_servicio': soporte.fecha_hora_servicio.strftime('%d/%m/%Y %H:%M') if soporte.fecha_hora_servicio else 'No registrada',
        'fecha_creacion': soporte.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        'fecha_actualizacion': soporte.fecha_actualizacion.strftime('%d/%m/%Y %H:%M'),
        
        # Información del cliente
        'cliente_nombre': soporte.nombre_cliente,
        'cliente_cedula': soporte.cedula_cliente,
        'direccion': soporte.direccion,
        'customer_id': soporte.customer_id or 'N/A',
        'plan': soporte.plan or 'N/A',
        'atr': soporte.atr or 'N/A',
        
        # Datos del soporte
        'falla_encontrada': soporte.falla_encontrada,
        'solucion': soporte.solucion,
        'observaciones': soporte.observaciones or '',
        
        # Datos del módem
        'modelo_modem': soporte.modelo_modem.nombre if soporte.modelo_modem else 'No se cambió',
        'sn_modem': soporte.sn_modem or 'No se cambió',
        'mac_modem': soporte.mac_modem or 'No se cambió',
        
        # Materiales
        'inicio_fibra': soporte.inicio_fibra or 0,
        'final_fibra': soporte.final_fibra or 0,
        'metros_utilizados': soporte.metros_utilizados,
        'conectores': soporte.conectores or 0,
        'rosetas': soporte.rosetas or 0,
        'patch_cord': soporte.patch_cord or 0,
        'tensores': soporte.tensores or 0,
        'conectores_malos': soporte.conectores_malos or 0,
        
        # Datos NAP
        'caja_nap_utilizada': soporte.caja_nap_utilizada or 'N/A',
        'puerto_nap_utilizado': soporte.puerto_nap_utilizado or 'N/A',
        
        # Ubicación
        'pin_ubicacion_lat': soporte.pin_ubicacion_lat,
        'pin_ubicacion_lng': soporte.pin_ubicacion_lng,
        'pin_ubicacion_url': f"https://www.google.com/maps?q={soporte.pin_ubicacion_lat},{soporte.pin_ubicacion_lng}" if soporte.pin_ubicacion_lat and soporte.pin_ubicacion_lng else None,
        
        # Fotos
        'fotos': soporte.fotos or [],
        
        # Instaladores
        'instaladores': instaladores_lista,
        
        # Cuadrilla
        'cuadrilla': soporte.cuadrilla.nombre if soporte.cuadrilla else 'No asignada',
        
        # Permisos
        'puede_editar': soporte.estado not in ['COMPLETADO', 'CANCELADO'],
    }
    
    return JsonResponse(data)    

@login_required
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Administrador').exists())
def instalacion_por_contrato(request, contrato_id):
    """Obtiene la instalación asociada a un contrato"""
    try:
        # Buscar la asignación que tiene este contrato
        asignacion = AsignacionContrato.objects.filter(contrato_id=contrato_id).first()
        
        if asignacion:
            # Buscar la instalación asociada a esta asignación
            instalacion = Instalacion.objects.filter(asignacion=asignacion).first()
            if instalacion:
                return JsonResponse({'instalacion_id': instalacion.id})
        
        return JsonResponse({'instalacion_id': None})
    except Exception as e:
        return JsonResponse({'instalacion_id': None, 'error': str(e)})