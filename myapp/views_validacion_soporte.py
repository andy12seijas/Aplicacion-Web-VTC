import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import SoporteCliente, ContratoCliente, ClienteExterno


@staff_member_required
def gestion_soportes_cliente(request):
    """Vista para gestionar los soportes/reclamos de clientes (Call Center)"""
    
    # Obtener parámetros
    busqueda = request.GET.get('busqueda', '')
    tab_activa = request.GET.get('tab', 'no_leidos')
    page_no_leidos = request.GET.get('page_no_leidos', 1)
    page_leidos = request.GET.get('page_leidos', 1)
    
    # Soportes NO LEIDOS
    soportes_no_leidos = SoporteCliente.objects.filter(
        estado='NO_LEIDO'
    ).select_related('contrato__cliente_potencial', 'cliente_externo').order_by('-fecha_creacion')
    
    # Soportes LEIDOS
    soportes_leidos = SoporteCliente.objects.filter(
        estado='LEIDO'
    ).select_related('contrato__cliente_potencial', 'cliente_externo').order_by('-fecha_creacion')
    
    # Aplicar búsqueda
    if busqueda:
        soportes_no_leidos = soportes_no_leidos.filter(
            Q(contrato__cliente_potencial__nombre__icontains=busqueda) |
            Q(contrato__cliente_potencial__apellido__icontains=busqueda) |
            Q(contrato__cliente_potencial__cedula__icontains=busqueda) |
            Q(cliente_externo__nombre__icontains=busqueda) |
            Q(cliente_externo__apellido__icontains=busqueda) |
            Q(cliente_externo__cedula__icontains=busqueda) |
            Q(reclamo__icontains=busqueda)
        )
        
        soportes_leidos = soportes_leidos.filter(
            Q(contrato__cliente_potencial__nombre__icontains=busqueda) |
            Q(contrato__cliente_potencial__apellido__icontains=busqueda) |
            Q(contrato__cliente_potencial__cedula__icontains=busqueda) |
            Q(cliente_externo__nombre__icontains=busqueda) |
            Q(cliente_externo__apellido__icontains=busqueda) |
            Q(cliente_externo__cedula__icontains=busqueda) |
            Q(reclamo__icontains=busqueda)
        )
    
    # Paginación
    paginator_no_leidos = Paginator(soportes_no_leidos, 15)
    paginator_leidos = Paginator(soportes_leidos, 15)
    
    try:
        soportes_no_leidos_page = paginator_no_leidos.page(page_no_leidos)
    except (PageNotAnInteger, EmptyPage):
        soportes_no_leidos_page = paginator_no_leidos.page(1)
    
    try:
        soportes_leidos_page = paginator_leidos.page(page_leidos)
    except (PageNotAnInteger, EmptyPage):
        soportes_leidos_page = paginator_leidos.page(1)
    
    # Estadísticas
    stats = {
        'no_leidos': SoporteCliente.objects.filter(estado='NO_LEIDO').count(),
        'leidos': SoporteCliente.objects.filter(estado='LEIDO').count(),
        'total': SoporteCliente.objects.all().count(),
    }
    
    context = {
        'soportes_no_leidos': soportes_no_leidos_page,
        'soportes_leidos': soportes_leidos_page,
        'stats': stats,
        'busqueda': busqueda,
        'tab_activa': tab_activa,
    }
    
    return render(request, 'Admin/validacion_soporte.html', context)


@csrf_exempt
@staff_member_required
def marcar_soporte_leido(request, soporte_id):
    """Marca un soporte como leído"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        soporte = get_object_or_404(SoporteCliente, id=soporte_id)
        
        if soporte.estado == 'LEIDO':
            return JsonResponse({'error': 'Este soporte ya está marcado como leído'}, status=400)
        
        soporte.marcar_como_leido()
        
        return JsonResponse({
            'success': True,
            'message': 'Soporte marcado como leído correctamente'
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
def ver_detalle_soporte(request, soporte_id):
    """Obtiene los detalles de un soporte para mostrar en el modal"""
    
    soporte = get_object_or_404(SoporteCliente, id=soporte_id)
    
    # Obtener datos del cliente
    if soporte.contrato:
        cliente_nombre = soporte.contrato.nombre_completo
        cliente_cedula = soporte.contrato.cedula
        cliente_telefono = soporte.contrato.telefono_principal
        cliente_correo = soporte.contrato.correo_electronico
        plan = soporte.contrato.plan_contratado.nombre if soporte.contrato.plan_contratado else 'N/A'
        tipo_cliente = 'Cliente con contrato'
    elif soporte.cliente_externo:
        cliente_nombre = soporte.cliente_externo.nombre_completo
        cliente_cedula = soporte.cliente_externo.cedula
        cliente_telefono = soporte.cliente_externo.telefono
        cliente_correo = soporte.cliente_externo.correo
        plan = 'N/A (Cliente externo)'
        tipo_cliente = 'Cliente externo'
    else:
        cliente_nombre = 'Cliente no disponible'
        cliente_cedula = 'N/A'
        cliente_telefono = 'N/A'
        cliente_correo = 'N/A'
        plan = 'N/A'
        tipo_cliente = 'Desconocido'
    
    data = {
        'id': soporte.id,
        'cliente_nombre': cliente_nombre,
        'cliente_cedula': cliente_cedula,
        'cliente_telefono': cliente_telefono,
        'cliente_correo': cliente_correo,
        'plan': plan,
        'tipo_cliente': tipo_cliente,
        'reclamo': soporte.reclamo,
        'observacion': soporte.observacion or 'Sin observaciones',
        'foto_url': soporte.foto.url if soporte.foto else None,
        'estado': soporte.estado,
        'estado_display': soporte.get_estado_display(),
        'fecha_creacion': soporte.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        'fecha_leido': soporte.fecha_leido.strftime('%d/%m/%Y %H:%M') if soporte.fecha_leido else None,
        'creado_por': soporte.creado_por.get_full_name() or soporte.creado_por.username if soporte.creado_por else 'Cliente',
    }
    
    return JsonResponse(data)