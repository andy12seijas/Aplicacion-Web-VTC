import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import (
    ContratoCliente, ClienteExterno, ReportePago, 
    DetallePagoMovil, DetalleTransferencia, Banco
)
from .forms import ClienteExternoForm
import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import ReportePago, RegistroValidacionPago, ContratoCliente, ClienteExterno, Banco
from django.contrib.auth.models import User

def reportar_pago(request):
    """Vista principal para reportar pagos"""
    bancos = Banco.objects.filter(activo=True)
    # Filtrar solo Banplus y Banco Nacional de Crédito para bancos receptores
    bancos_receptores = Banco.objects.filter(
        activo=True,
        codigo__in=['0174', '0191']  # 0174 = Banplus, 0191 = Banco Nacional de Crédito
    )
    return render(request, 'pagos/reportar_pago.html', {
        'bancos': bancos,
        'bancos_receptores': bancos_receptores
    })


@csrf_exempt
@require_http_methods(["POST"])
def buscar_cliente(request):
    """Busca cliente por cédula y correo"""
    try:
        data = json.loads(request.body)
        cedula = data.get('cedula')
        correo = data.get('correo')
        
        # Buscar en ContratoCliente (clientes internos)
        contrato = ContratoCliente.objects.filter(
            cliente_potencial__cedula=cedula,
            correo_electronico=correo
        ).select_related('cliente_potencial').first()
        
        if contrato:
            return JsonResponse({
                'exists': True,
                'cliente': {
                    'tipo': 'INTERNO',
                    'id': contrato.id,
                    'cedula': contrato.cedula,
                    'nombre_completo': contrato.nombre_completo,
                    'nombre': contrato.nombre,
                    'apellido': contrato.apellido,
                    'telefono': contrato.telefono_principal,
                    'correo': contrato.correo_electronico
                }
            })
        
        # Buscar en ClienteExterno
        cliente_externo = ClienteExterno.objects.filter(
            cedula=cedula,
            correo=correo
        ).first()
        
        if cliente_externo:
            return JsonResponse({
                'exists': True,
                'cliente': {
                    'tipo': 'EXTERNO',
                    'id': cliente_externo.id,
                    'cedula': cliente_externo.cedula,
                    'nombre_completo': cliente_externo.nombre_completo,
                    'nombre': cliente_externo.nombre,
                    'apellido': cliente_externo.apellido,
                    'telefono': cliente_externo.telefono,
                    'correo': cliente_externo.correo
                }
            })
        
        return JsonResponse({'exists': False})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def registrar_cliente_externo(request):
    """Registra un nuevo cliente externo"""
    try:
        form = ClienteExternoForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            return JsonResponse({
                'success': True,
                'cliente_id': cliente.id
            })
        else:
            return JsonResponse({
                'success': False,
                'error': form.errors
            }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def crear_reporte(request):
    """Crea el reporte de pago completo"""
    try:
        # Datos básicos del reporte
        medio_pago = request.POST.get('medio_pago')
        monto = request.POST.get('monto')
        fecha_pago = request.POST.get('fecha_pago')
        observacion_cliente = request.POST.get('observacion_cliente', '')
        comprobante = request.FILES.get('comprobante')
        tipo_cliente = request.POST.get('tipo_cliente')
        
        # Crear reporte
        reporte = ReportePago(
            medio_pago=medio_pago,
            monto=monto,
            fecha_pago=fecha_pago,
            observacion_cliente=observacion_cliente,
            comprobante=comprobante,
            tipo_cliente=tipo_cliente,
            ip_cliente=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Asociar cliente
        if tipo_cliente == 'INTERNO':
            contrato_id = request.POST.get('contrato_id')
            reporte.contrato_id = contrato_id
        else:
            cliente_externo_id = request.POST.get('cliente_externo_id')
            reporte.cliente_externo_id = cliente_externo_id
        
        reporte.save()
        
        # Crear detalle según método de pago
        if medio_pago == 'PAGO_MOVIL':
            detalle = DetallePagoMovil.objects.create(
                banco_emisor_id=request.POST.get('banco_emisor'),
                banco_receptor_id=request.POST.get('banco_receptor'),
                numero_telefono=request.POST.get('numero_telefono'),
                cedula_titular=request.POST.get('cedula_titular'),
                referencia=request.POST.get('referencia')
            )
            reporte.detalle_pago_movil = detalle
        
        elif medio_pago == 'TRANSFERENCIA':
            detalle = DetalleTransferencia.objects.create(
                banco_origen_id=request.POST.get('banco_origen'),
                banco_destino_id=request.POST.get('banco_destino'),
                cedula_titular=request.POST.get('cedula_titular'),
                numero_cuenta_origen=request.POST.get('numero_cuenta_origen', ''),
                referencia=request.POST.get('referencia')
            )
            reporte.detalle_transferencia = detalle
        
        reporte.save()
        
        return JsonResponse({'success': True, 'reporte_id': reporte.id})
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def exito(request):
    """Página de éxito después de reportar pago"""
    # Aquí podrías obtener el último reporte de la sesión
    return render(request, 'pagos/exito.html')




import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import ReportePago, RegistroValidacionPago, ContratoCliente, ClienteExterno, Banco



def validacion_pagos(request):
    """Vista para el panel de validación de pagos (Call Center)"""
    
    # Obtener parámetros de la URL
    busqueda = request.GET.get('busqueda', '')
    tab_activa = request.GET.get('tab', 'pendientes')
    
    # Obtener página actual para cada tabla
    page_pendientes = request.GET.get('page_pendientes', 1)
    page_completados = request.GET.get('page_completados', 1)
    
    # Reportes PENDIENTES
    reportes_pendientes = ReportePago.objects.filter(estado='PENDIENTE').select_related(
        'contrato__cliente_potencial', 'cliente_externo', 'detalle_pago_movil', 'detalle_transferencia'
    ).order_by('-fecha_reporte')
    
    # Reportes COMPLETADOS (Verificados, Rechazados, Aplicados)
    reportes_completados = ReportePago.objects.filter(
        estado__in=['VERIFICADO', 'RECHAZADO', 'APLICADO']
    ).select_related(
        'contrato__cliente_potencial', 'cliente_externo', 'detalle_pago_movil', 'detalle_transferencia'
    ).order_by('-fecha_verificacion')
    
    # Aplicar filtro de búsqueda
    if busqueda:
        reportes_pendientes = reportes_pendientes.filter(
            Q(contrato__cliente_potencial__nombre__icontains=busqueda) |
            Q(contrato__cliente_potencial__apellido__icontains=busqueda) |
            Q(contrato__cliente_potencial__cedula__icontains=busqueda) |
            Q(cliente_externo__nombre__icontains=busqueda) |
            Q(cliente_externo__apellido__icontains=busqueda) |
            Q(cliente_externo__cedula__icontains=busqueda) |
            Q(detalle_pago_movil__referencia__icontains=busqueda) |
            Q(detalle_transferencia__referencia__icontains=busqueda)
        )
        
        reportes_completados = reportes_completados.filter(
            Q(contrato__cliente_potencial__nombre__icontains=busqueda) |
            Q(contrato__cliente_potencial__apellido__icontains=busqueda) |
            Q(contrato__cliente_potencial__cedula__icontains=busqueda) |
            Q(cliente_externo__nombre__icontains=busqueda) |
            Q(cliente_externo__apellido__icontains=busqueda) |
            Q(cliente_externo__cedula__icontains=busqueda) |
            Q(detalle_pago_movil__referencia__icontains=busqueda) |
            Q(detalle_transferencia__referencia__icontains=busqueda)
        )
    
    # Paginación - PENDIENTES
    paginator_pendientes = Paginator(reportes_pendientes, 15)
    try:
        reportes_pendientes_page = paginator_pendientes.page(page_pendientes)
    except PageNotAnInteger:
        reportes_pendientes_page = paginator_pendientes.page(1)
    except EmptyPage:
        reportes_pendientes_page = paginator_pendientes.page(paginator_pendientes.num_pages)
    
    # Paginación - COMPLETADOS
    paginator_completados = Paginator(reportes_completados, 15)
    try:
        reportes_completados_page = paginator_completados.page(page_completados)
    except PageNotAnInteger:
        reportes_completados_page = paginator_completados.page(1)
    except EmptyPage:
        reportes_completados_page = paginator_completados.page(paginator_completados.num_pages)
    
    # Estadísticas
    stats = {
        'pendientes': ReportePago.objects.filter(estado='PENDIENTE').count(),
        'verificados': ReportePago.objects.filter(estado='VERIFICADO').count(),
        'rechazados': ReportePago.objects.filter(estado='RECHAZADO').count(),
        'aplicados': ReportePago.objects.filter(estado='APLICADO').count(),
        'total_mes': ReportePago.objects.filter(fecha_reporte__month=timezone.now().month).count(),
    }
    
    context = {
        'reportes_pendientes': reportes_pendientes_page,
        'reportes_completados': reportes_completados_page,
        'stats': stats,
        'busqueda': busqueda,
        'tab_activa': tab_activa,
    }
    
    return render(request, 'pagos/validacion_pagos.html', context)



def obtener_detalle_pago(request, reporte_id):
    """Obtiene los detalles de un reporte de pago para mostrar en el modal"""
    
    reporte = get_object_or_404(ReportePago, id=reporte_id)
    
    # Obtener datos del cliente según el tipo
    if reporte.es_cliente_interno and reporte.contrato:
        cliente_nombre = reporte.contrato.nombre_completo
        cliente_cedula = reporte.contrato.cedula
        cliente_telefono = reporte.contrato.telefono_principal
        cliente_correo = reporte.contrato.correo_electronico
        plan = reporte.contrato.plan_contratado.nombre if reporte.contrato.plan_contratado else 'N/A'
    elif reporte.cliente_externo:
        cliente_nombre = reporte.cliente_externo.nombre_completo
        cliente_cedula = reporte.cliente_externo.cedula
        cliente_telefono = reporte.cliente_externo.telefono
        cliente_correo = reporte.cliente_externo.correo
        plan = 'N/A (Cliente externo)'
    else:
        cliente_nombre = 'Cliente no disponible'
        cliente_cedula = 'N/A'
        cliente_telefono = 'N/A'
        cliente_correo = 'N/A'
        plan = 'N/A'
    
    # Obtener detalles según el método de pago
    detalle_data = {}
    if reporte.medio_pago == 'PAGO_MOVIL' and reporte.detalle_pago_movil:
        detalle = reporte.detalle_pago_movil
        detalle_data = {
            'banco_emisor': detalle.banco_emisor.nombre if detalle.banco_emisor else 'N/A',
            'banco_receptor': detalle.banco_receptor.nombre if detalle.banco_receptor else 'N/A',
            'numero_telefono': detalle.numero_telefono,
            'cedula_titular': detalle.cedula_titular,
            'referencia': detalle.referencia,
        }
    elif reporte.medio_pago == 'TRANSFERENCIA' and reporte.detalle_transferencia:
        detalle = reporte.detalle_transferencia
        detalle_data = {
            'banco_origen': detalle.banco_origen.nombre if detalle.banco_origen else 'N/A',
            'banco_destino': detalle.banco_destino.nombre if detalle.banco_destino else 'N/A',
            'cedula_titular': detalle.cedula_titular,
            'numero_cuenta_origen': detalle.numero_cuenta_origen or 'No especificado',
            'referencia': detalle.referencia,
        }
    
    # Obtener historial de validaciones
    validaciones = []
    for v in reporte.validaciones.all().order_by('-fecha_validacion'):
        validaciones.append({
            'accion': v.get_accion_display(),
            'fecha': v.fecha_validacion.strftime('%d/%m/%Y %H:%M'),
            'validado_por': v.validado_por.get_full_name() or v.validado_por.username if v.validado_por else 'Sistema',
            'nota_interna': v.nota_interna or 'Sin observaciones'
        })
    
    data = {
        'id': reporte.id,
        'cliente_nombre': cliente_nombre,
        'cliente_cedula': cliente_cedula,
        'cliente_telefono': cliente_telefono,
        'cliente_correo': cliente_correo,
        'plan': plan,
        'tipo_cliente': reporte.get_tipo_cliente_display(),
        'medio_pago': reporte.get_medio_pago_display(),
        'monto': float(reporte.monto),
        'fecha_pago': reporte.fecha_pago.strftime('%d/%m/%Y'),
        'fecha_reporte': reporte.fecha_reporte.strftime('%d/%m/%Y %H:%M'),
        'referencia': detalle_data.get('referencia', 'N/A'),
        'comprobante_url': reporte.comprobante.url if reporte.comprobante else None,
        'observacion_cliente': reporte.observacion_cliente or 'Sin observaciones',
        'estado': reporte.estado,
        'estado_display': reporte.get_estado_display(),
        'detalle': detalle_data,
        'validaciones': validaciones,
    }
    
    return JsonResponse(data)


@csrf_exempt

def aprobar_pago(request, reporte_id):
    """Aprueba un pago y lo marca como VERIFICADO"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        reporte = get_object_or_404(ReportePago, id=reporte_id)
        
        if reporte.estado != 'PENDIENTE':
            return JsonResponse({'error': 'Este pago ya ha sido procesado'}, status=400)
        
        # Actualizar estado del reporte
        reporte.estado = 'VERIFICADO'
        reporte.fecha_verificacion = timezone.now()
        reporte.verificado_por = request.user
        reporte.save()
        
        # Registrar la validación en el historial
        RegistroValidacionPago.objects.create(
            reporte=reporte,
            accion='VERIFICADO',
            validado_por=request.user,
            nota_interna='Pago verificado correctamente'
        )
        
        return JsonResponse({'success': True, 'message': 'Pago aprobado correctamente'})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt

def rechazar_pago(request, reporte_id):
    """Rechaza un pago y guarda el motivo"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        motivo = data.get('motivo', '')
        
        if not motivo:
            return JsonResponse({'error': 'Debes especificar un motivo de rechazo'}, status=400)
        
        reporte = get_object_or_404(ReportePago, id=reporte_id)
        
        if reporte.estado != 'PENDIENTE':
            return JsonResponse({'error': 'Este pago ya ha sido procesado'}, status=400)
        
        # Actualizar estado del reporte
        reporte.estado = 'RECHAZADO'
        reporte.rechazo_motivo = motivo
        reporte.fecha_verificacion = timezone.now()
        reporte.verificado_por = request.user
        reporte.save()
        
        # Registrar la validación en el historial
        RegistroValidacionPago.objects.create(
            reporte=reporte,
            accion='RECHAZADO',
            validado_por=request.user,
            nota_interna=motivo
        )
        
        return JsonResponse({'success': True, 'message': 'Pago rechazado correctamente'})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)