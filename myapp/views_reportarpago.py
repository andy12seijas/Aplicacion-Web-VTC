import json
from pyexpat.errors import messages
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone

from myapp.views_admin import es_admin
from .models import (
    ClientePotencial, ContratoCliente, ClienteExterno, RegistroLlamada, ReportePago, 
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
                numero_telefono=request.POST.get('numero_telefono'),
               
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
    tipo_cliente = request.GET.get('tipo_cliente', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
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
    
    # Aplicar filtro de tipo de cliente
    if tipo_cliente == 'interno':
        reportes_pendientes = reportes_pendientes.filter(contrato__isnull=False)
        reportes_completados = reportes_completados.filter(contrato__isnull=False)
    elif tipo_cliente == 'externo':
        reportes_pendientes = reportes_pendientes.filter(contrato__isnull=True)
        reportes_completados = reportes_completados.filter(contrato__isnull=True)
    
    # Aplicar filtro de fechas
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            reportes_pendientes = reportes_pendientes.filter(fecha_pago__gte=fecha_desde_obj)
            reportes_completados = reportes_completados.filter(fecha_pago__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            reportes_pendientes = reportes_pendientes.filter(fecha_pago__lte=fecha_hasta_obj)
            reportes_completados = reportes_completados.filter(fecha_pago__lte=fecha_hasta_obj)
        except ValueError:
            pass
    
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
        'tipo_cliente': tipo_cliente,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
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
            
            'numero_telefono': detalle.numero_telefono,
           
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
    



@login_required
def reporte_clientes_callcenter(request):
    """Vista para reporte unificado de clientes (Contratos, Potenciales sin contrato, Externos) para Call Center"""
    
    import pytz
    from datetime import datetime
    from django.core.paginator import Paginator
    from django.db.models import Q, Exists, OuterRef
    
    VE_TZ = pytz.timezone('America/Caracas')
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_callcenter = request.user.groups.filter(name='Call Center').exists()
    
    if not (es_admin or es_callcenter):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Obtener parámetros de filtro
    tipo_cliente = request.GET.get('tipo', 'todos')
    busqueda = request.GET.get('busqueda', '')
    filtro_estado = request.GET.get('estado_llamada', '')
    
    from django.db.models import OuterRef, Subquery
    
    # ========== 1. CONTRATOS ==========
    contratos = ContratoCliente.objects.select_related(
        'cliente_potencial', 'creado_por', 'plan_contratado'
    )
    
    ultima_llamada_contrato = RegistroLlamada.objects.filter(
        contrato=OuterRef('pk')
    ).order_by('-fecha_llamada')
    
    contratos = contratos.annotate(
        ultimo_estado=Subquery(ultima_llamada_contrato.values('estado')[:1]),
        ultima_nota=Subquery(ultima_llamada_contrato.values('nota')[:1]),
        ultima_fecha=Subquery(ultima_llamada_contrato.values('fecha_llamada')[:1])
    )
    
    # ========== 2. CLIENTES POTENCIALES (SOLO SIN CONTRATO) ==========
    potenciales = ClientePotencial.objects.filter(
        ~Exists(ContratoCliente.objects.filter(cliente_potencial=OuterRef('pk')))
    ).select_related('creado_por')
    
    ultima_llamada_potencial = RegistroLlamada.objects.filter(
        cliente_potencial=OuterRef('pk')
    ).order_by('-fecha_llamada')
    
    potenciales = potenciales.annotate(
        ultimo_estado=Subquery(ultima_llamada_potencial.values('estado')[:1]),
        ultima_nota=Subquery(ultima_llamada_potencial.values('nota')[:1]),
        ultima_fecha=Subquery(ultima_llamada_potencial.values('fecha_llamada')[:1])
    )
    
    # ========== 3. CLIENTES EXTERNOS ==========
    externos = ClienteExterno.objects.all()
    
    ultima_llamada_externo = RegistroLlamada.objects.filter(
        cliente_externo=OuterRef('pk')
    ).order_by('-fecha_llamada')
    
    externos = externos.annotate(
        ultimo_estado=Subquery(ultima_llamada_externo.values('estado')[:1]),
        ultima_nota=Subquery(ultima_llamada_externo.values('nota')[:1]),
        ultima_fecha=Subquery(ultima_llamada_externo.values('fecha_llamada')[:1])
    )
    
    # ========== UNIFICAR TODOS LOS CLIENTES ==========
    todos_clientes = []
    
    for c in contratos:
        estado = c.ultimo_estado or 'PENDIENTE'
        todos_clientes.append({
            'id': c.id,
            'tipo': 'CONTRATO',
            'nombre': c.nombre_completo,
            'cedula': c.cedula,
            'telefono': c.telefono_principal,
            'telefono_secundario': c.otro_telefono or '',
            'vendedor': c.creado_por.get_full_name() or c.creado_por.username if c.creado_por else 'N/A',
            'fecha_registro': c.fecha_creacion,
            'fecha_completado': c.fecha_completado.astimezone(VE_TZ).strftime('%d/%m/%Y') if c.fecha_completado else 'En proceso',
            'estado_llamada': estado,
            'ultima_nota': c.ultima_nota or '',
            'ultima_fecha': c.ultima_fecha.astimezone(VE_TZ).strftime('%d/%m/%Y %H:%M') if c.ultima_fecha else '',
        })
    
    for p in potenciales:
        estado = p.ultimo_estado or 'PENDIENTE'
        todos_clientes.append({
            'id': p.id,
            'tipo': 'POTENCIAL',
            'nombre': p.nombre_completo,
            'cedula': p.cedula,
            'telefono': p.telefono,
            'telefono_secundario': '',
            'vendedor': p.creado_por.get_full_name() or p.creado_por.username if p.creado_por else 'N/A',
            'fecha_registro': p.fecha_creacion,
            'fecha_completado': 'Sin contrato',
            'estado_llamada': estado,
            'ultima_nota': p.ultima_nota or '',
            'ultima_fecha': p.ultima_fecha.astimezone(VE_TZ).strftime('%d/%m/%Y %H:%M') if p.ultima_fecha else '',
        })
    
    for e in externos:
        estado = e.ultimo_estado or 'PENDIENTE'
        todos_clientes.append({
            'id': e.id,
            'tipo': 'EXTERNO',
            'nombre': e.nombre_completo,
            'cedula': e.cedula,
            'telefono': e.telefono,
            'telefono_secundario': '',
            'vendedor': 'Call Center',
            'fecha_registro': e.fecha_registro,
            'fecha_completado': 'Sin contrato',
            'estado_llamada': estado,
            'ultima_nota': e.ultima_nota or '',
            'ultima_fecha': e.ultima_fecha.strftime('%d/%m/%Y %H:%M') if e.ultima_fecha else '',
        })
    
    # Filtrar por tipo
    if tipo_cliente == 'contratos':
        todos_clientes = [c for c in todos_clientes if c['tipo'] == 'CONTRATO']
    elif tipo_cliente == 'potenciales':
        todos_clientes = [c for c in todos_clientes if c['tipo'] == 'POTENCIAL']
    elif tipo_cliente == 'externos':
        todos_clientes = [c for c in todos_clientes if c['tipo'] == 'EXTERNO']
    
    # Filtrar por búsqueda
    if busqueda:
        busqueda_lower = busqueda.lower()
        todos_clientes = [
            c for c in todos_clientes
            if (busqueda_lower in c['nombre'].lower() or
                busqueda_lower in c['cedula'].lower() or
                busqueda_lower in c['telefono'].lower())
        ]
    
    # Filtrar por estado de llamada
    if filtro_estado:
        todos_clientes = [c for c in todos_clientes if c['estado_llamada'] == filtro_estado]
    
    # Ordenar por fecha de registro (más reciente primero)
    todos_clientes.sort(key=lambda x: x['fecha_registro'], reverse=True)
    
    # Paginación
    paginator = Paginator(todos_clientes, 15)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    
    # Estadísticas
    total_contratos = len([c for c in todos_clientes if c['tipo'] == 'CONTRATO'])
    total_potenciales = len([c for c in todos_clientes if c['tipo'] == 'POTENCIAL'])
    total_externos = len([c for c in todos_clientes if c['tipo'] == 'EXTERNO'])
    
    context = {
        'page_obj': page_obj,
        'total_clientes': len(todos_clientes),
        'total_contratos': total_contratos,
        'total_potenciales': total_potenciales,
        'total_externos': total_externos,
        'tipo_cliente': tipo_cliente,
        'busqueda': busqueda,
        'filtro_estado': filtro_estado,
        'es_admin': es_admin,
    }
    
    return render(request, 'pagos/reporte_clientes.html', context)


@login_required
def registrar_llamada(request):
    """API para registrar una llamada"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    import json
    data = json.loads(request.body)
    
    cliente_tipo = data.get('cliente_tipo')  # CONTRATO, POTENCIAL, EXTERNO
    cliente_id = data.get('cliente_id')
    estado = data.get('estado')  # CONTACTADO, NO_RESPONDE
    nota = data.get('nota', '')
    
    # Buscar el cliente según su tipo
    contrato = None
    cliente_potencial = None
    cliente_externo = None
    
    if cliente_tipo == 'CONTRATO':
        contrato = get_object_or_404(ContratoCliente, id=cliente_id)
    elif cliente_tipo == 'POTENCIAL':
        cliente_potencial = get_object_or_404(ClientePotencial, id=cliente_id)
    elif cliente_tipo == 'EXTERNO':
        cliente_externo = get_object_or_404(ClienteExterno, id=cliente_id)
    
    # Crear el registro de llamada
    llamada = RegistroLlamada.objects.create(
        contrato=contrato,
        cliente_potencial=cliente_potencial,
        cliente_externo=cliente_externo,
        estado=estado,
        nota=nota,
        realizado_por=request.user
    )
    
    return JsonResponse({
        'success': True,
        'estado': llamada.get_estado_display(),
        'fecha': llamada.fecha_llamada.strftime('%d/%m/%Y %H:%M')
    })    



@login_required
@user_passes_test(es_admin)
def reporte_llamadas_json(request):
    """API para reporte de llamadas del Call Center"""
    
    import pytz
    from datetime import datetime
    from django.core.paginator import Paginator
    
    VE_TZ = pytz.timezone('America/Caracas')
    
    tipo_reporte = request.GET.get('tipo', 'simple')
    fecha_desde_raw = request.GET.get('fecha_desde', '')
    fecha_hasta_raw = request.GET.get('fecha_hasta', '')
    estado = request.GET.get('estado', '')
    agente_id = request.GET.get('agente', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 15))
    
    # Convertir fechas
    fecha_desde_obj = None
    fecha_hasta_obj = None
    
    if fecha_desde_raw:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde_raw, '%Y-%m-%d').date()
        except:
            pass
    
    if fecha_hasta_raw:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta_raw, '%Y-%m-%d').date()
        except:
            pass
    
    llamadas = RegistroLlamada.objects.select_related(
        'contrato__cliente_potencial',
        'cliente_potencial',
        'cliente_externo',
        'realizado_por'
    )
    
    if fecha_desde_obj and fecha_hasta_obj:
        llamadas = llamadas.filter(
            fecha_llamada__date__gte=fecha_desde_obj,
            fecha_llamada__date__lte=fecha_hasta_obj
        )
    elif fecha_desde_obj:
        llamadas = llamadas.filter(fecha_llamada__date__gte=fecha_desde_obj)
    elif fecha_hasta_obj:
        llamadas = llamadas.filter(fecha_llamada__date__lte=fecha_hasta_obj)
    
    if estado:
        llamadas = llamadas.filter(estado=estado)
    if agente_id:
        llamadas = llamadas.filter(realizado_por_id=agente_id)
    
    total_registros = llamadas.count()
    paginator = Paginator(llamadas, per_page)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    def obtener_cliente(llamada):
        if llamada.contrato:
            return {
                'nombre': llamada.contrato.nombre_completo,
                'cedula': llamada.contrato.cedula,
                'telefono': llamada.contrato.telefono_principal,
                'tipo': 'CONTRATO'
            }
        elif llamada.cliente_potencial:
            return {
                'nombre': llamada.cliente_potencial.nombre_completo,
                'cedula': llamada.cliente_potencial.cedula,
                'telefono': llamada.cliente_potencial.telefono,
                'tipo': 'POTENCIAL'
            }
        elif llamada.cliente_externo:
            return {
                'nombre': llamada.cliente_externo.nombre_completo,
                'cedula': llamada.cliente_externo.cedula,
                'telefono': llamada.cliente_externo.telefono,
                'tipo': 'EXTERNO'
            }
        return None
    
    if tipo_reporte == 'simple':
        data_list = []
        for llamada in page_obj:
            cliente = obtener_cliente(llamada)
            data_list.append({
                'id': llamada.id,
                'cliente': cliente['nombre'] if cliente else 'N/A',
                'telefono': cliente['telefono'] if cliente else 'N/A',
                'estado': llamada.get_estado_display(),
                'fecha': llamada.fecha_llamada.astimezone(VE_TZ).strftime('%d/%m/%Y %H:%M'),
                'agente': llamada.realizado_por.get_full_name() or llamada.realizado_por.username if llamada.realizado_por else 'Sistema'
            })
    else:
        data_list = []
        for llamada in page_obj:
            cliente = obtener_cliente(llamada)
            data_list.append({
                'id': llamada.id,
                'cliente': cliente['nombre'] if cliente else 'N/A',
                'cedula': cliente['cedula'] if cliente else 'N/A',
                'telefono': cliente['telefono'] if cliente else 'N/A',
                'tipo_cliente': cliente['tipo'] if cliente else 'N/A',
                'estado': llamada.get_estado_display(),
                'nota': llamada.nota or 'N/A',
                'fecha': llamada.fecha_llamada.astimezone(VE_TZ).strftime('%d/%m/%Y %H:%M'),
                'agente': llamada.realizado_por.get_full_name() or llamada.realizado_por.username if llamada.realizado_por else 'Sistema'
            })
    
    estadisticas = {
        'total_llamadas': total_registros,
        'contactados': llamadas.filter(estado='CONTACTADO').count(),
        'no_responde': llamadas.filter(estado='NO_RESPONDE').count(),
        'pendientes': llamadas.filter(estado='PENDIENTE').count(),
    }
    
    return JsonResponse({
        'data': data_list,
        'estadisticas': estadisticas,
        'total_registros': total_registros,
        'total_paginas': paginator.num_pages,
        'pagina_actual': page_obj.number,
        'por_pagina': per_page,
    })


@login_required
def api_clientes_callcenter(request):
    """API para obtener clientes filtrados por el tipo seleccionado"""
    
    import pytz
    from datetime import datetime
    from django.core.paginator import Paginator
    from django.db.models import Q, OuterRef, Subquery, Exists
    
    VE_TZ = pytz.timezone('America/Caracas')
    
    tipo = request.GET.get('tipo', 'todos')  # todos, contratos, potenciales, externos
    busqueda = request.GET.get('busqueda', '')
    estado_llamada = request.GET.get('estado_llamada', '')
    interes = request.GET.get('interes', '')
    fecha_desde_raw = request.GET.get('fecha_desde', '')
    fecha_hasta_raw = request.GET.get('fecha_hasta', '')
    page = int(request.GET.get('page', 1))
    per_page = 15
    
    # Convertir fechas
    fecha_desde_obj = None
    fecha_hasta_obj = None
    
    if fecha_desde_raw:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde_raw, '%Y-%m-%d').date()
        except:
            pass
    
    if fecha_hasta_raw:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta_raw, '%Y-%m-%d').date()
        except:
            pass
    
    clientes_list = []
    
    # ========== 1. SOLO CONTRATOS ==========
    if tipo == 'contratos' or tipo == 'todos':
        contratos = ContratoCliente.objects.select_related('cliente_potencial', 'creado_por')
        
        for c in contratos:
            # Filtrar por fecha
            if fecha_desde_obj and c.fecha_creacion.date() < fecha_desde_obj:
                continue
            if fecha_hasta_obj and c.fecha_creacion.date() > fecha_hasta_obj:
                continue
            
            # Obtener última llamada
            ultima = RegistroLlamada.objects.filter(contrato=c).order_by('-fecha_llamada').first()
            
            clientes_list.append({
                'id': c.id,
                'tipo': 'CONTRATO',
                'nombre': c.nombre_completo,
                'cedula': c.cedula,
                'telefono': c.telefono_principal,
                'telefono_secundario': c.otro_telefono or '',
                'vendedor': c.creado_por.get_full_name() or c.creado_por.username if c.creado_por else 'N/A',
                'fecha_registro': c.fecha_creacion.astimezone(VE_TZ).strftime('%d/%m/%Y %H:%M'),
                'fecha_completado': c.fecha_completado.astimezone(VE_TZ).strftime('%d/%m/%Y') if c.fecha_completado else '',
                'interes': '',
                'estado_llamada': ultima.estado if ultima else 'PENDIENTE',
                'ultima_nota': ultima.nota or '' if ultima else '',
                'ultima_fecha': ultima.fecha_llamada.astimezone(VE_TZ).strftime('%d/%m/%Y %H:%M') if ultima and ultima.fecha_llamada else '',
            })
    
    # ========== 2. SOLO CLIENTES POTENCIALES (SIN CONTRATO) ==========
    if tipo == 'potenciales' or tipo == 'todos':
        # Filtrar solo clientes potenciales que NO tienen contrato
        potenciales = ClientePotencial.objects.filter(
            # Excluir los que tienen un contrato asociado
            ~Exists(ContratoCliente.objects.filter(cliente_potencial=OuterRef('pk')))
        ).select_related('creado_por')
        
        for p in potenciales:
            # Filtrar por interés
            if interes and p.interesado != interes:
                continue
            
            # Filtrar por fecha
            if fecha_desde_obj and p.fecha_creacion.date() < fecha_desde_obj:
                continue
            if fecha_hasta_obj and p.fecha_creacion.date() > fecha_hasta_obj:
                continue
            
            ultima = RegistroLlamada.objects.filter(cliente_potencial=p).order_by('-fecha_llamada').first()
            
            interes_texto = ''
            if p.interesado == 'SI':
                interes_texto = 'Sí'
            elif p.interesado == 'TAL_VEZ':
                interes_texto = 'Tal vez'
            elif p.interesado == 'NO':
                interes_texto = 'No'
            
            clientes_list.append({
                'id': p.id,
                'tipo': 'POTENCIAL',
                'nombre': p.nombre_completo,
                'cedula': p.cedula,
                'telefono': p.telefono,
                'telefono_secundario': '',
                'vendedor': p.creado_por.get_full_name() or p.creado_por.username if p.creado_por else 'N/A',
                'fecha_registro': p.fecha_creacion.astimezone(VE_TZ).strftime('%d/%m/%Y %H:%M'),
                'fecha_completado': '',
                'interes': interes_texto,
                'estado_llamada': ultima.estado if ultima else 'PENDIENTE',
                'ultima_nota': ultima.nota or '' if ultima else '',
                'ultima_fecha': ultima.fecha_llamada.astimezone(VE_TZ).strftime('%d/%m/%Y %H:%M') if ultima and ultima.fecha_llamada else '',
            })
    
    # ========== 3. SOLO CLIENTES EXTERNOS ==========
    if tipo == 'externos' or tipo == 'todos':
        externos = ClienteExterno.objects.all()
        
        for e in externos:
            # Filtrar por fecha
            if fecha_desde_obj and e.fecha_registro.date() < fecha_desde_obj:
                continue
            if fecha_hasta_obj and e.fecha_registro.date() > fecha_hasta_obj:
                continue
            
            ultima = RegistroLlamada.objects.filter(cliente_externo=e).order_by('-fecha_llamada').first()
            
            clientes_list.append({
                'id': e.id,
                'tipo': 'EXTERNO',
                'nombre': e.nombre_completo,
                'cedula': e.cedula,
                'telefono': e.telefono,
                'telefono_secundario': '',
                'vendedor': 'Call Center',
                'fecha_registro': e.fecha_registro.astimezone(VE_TZ).strftime('%d/%m/%Y %H:%M') if e.fecha_registro else '',
                'fecha_completado': '',
                'interes': '',
                'estado_llamada': ultima.estado if ultima else 'PENDIENTE',
                'ultima_nota': ultima.nota or '' if ultima else '',
                'ultima_fecha': ultima.fecha_llamada.astimezone(VE_TZ).strftime('%d/%m/%Y %H:%M') if ultima and ultima.fecha_llamada else '',
            })
    
    # Filtrar por búsqueda
    if busqueda:
        busqueda_lower = busqueda.lower()
        clientes_list = [
            c for c in clientes_list
            if (busqueda_lower in c['nombre'].lower() or
                busqueda_lower in c['cedula'].lower() or
                busqueda_lower in c['telefono'].lower())
        ]
    
    # Filtrar por estado de llamada
    if estado_llamada:
        clientes_list = [c for c in clientes_list if c['estado_llamada'] == estado_llamada]
    
    # Ordenar
    clientes_list.sort(key=lambda x: x['fecha_registro'], reverse=True)
    
    # Estadísticas
    total_registros = len(clientes_list)
    contactados = len([c for c in clientes_list if c['estado_llamada'] == 'CONTACTADO'])
    no_responde = len([c for c in clientes_list if c['estado_llamada'] == 'NO_RESPONDE'])
    pendientes = len([c for c in clientes_list if c['estado_llamada'] == 'PENDIENTE'])
    
    # Paginación
    start = (page - 1) * per_page
    end = start + per_page
    page_data = clientes_list[start:end]
    total_paginas = (total_registros + per_page - 1) // per_page
    
    return JsonResponse({
        'data': page_data,
        'estadisticas': {
            'total_registros': total_registros,
            'contactados': contactados,
            'no_responde': no_responde,
            'pendientes': pendientes,
        },
        'total_paginas': total_paginas,
        'pagina_actual': page,
        'por_pagina': per_page,
    })



    