from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Sum
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from io import BytesIO
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import ContratoCliente, Instalacion, PerfilUsuario, Soporte, TasaCambio, User, Plan, Cuadrilla, VentaDirecta, Material, MovimientoInventario, InventarioGlobal
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.core.management import call_command
from django.views.decorators.csrf import csrf_exempt
import json

def es_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name='Administrador').exists())


@login_required
@user_passes_test(es_admin)
def reportes_view(request):
    """Vista principal de reportes unificada"""
    from myapp.models import User, Plan, Cuadrilla, Material
    # En reportes_view, agrega:
    instaladores = User.objects.filter(groups__name='Instalador').distinct().order_by('first_name', 'username')
    vendedores = User.objects.filter(
            groups__name__in=['Vendedor', 'Supervisor', 'Instalador']
        ).distinct().order_by('first_name', 'username')
    planes = Plan.objects.filter(activo=True)
    cuadrillas = Cuadrilla.objects.filter(activo=True)
    materiales = Material.objects.filter(activo=True)
    
    context = {
        'vendedores': vendedores,
        'planes': planes,
        'cuadrillas': cuadrillas,
        'materiales': materiales,
         'instaladores': instaladores,
    }
    return render(request, 'Admin/reporte.html', context)


@login_required
@user_passes_test(es_admin)
def reporte_ventas_json(request):
    """API para obtener datos de ventas (incluye COMPLETADO y EN_PROCESO)"""
    
    tipo_reporte = request.GET.get('tipo', 'simple')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    vendedor_id = request.GET.get('vendedor', '')
    plan_id = request.GET.get('plan', '')
    busqueda = request.GET.get('busqueda', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 15))
    
    # Incluir COMPLETADO y EN_PROCESO
    ventas = ContratoCliente.objects.filter(estado__in=['COMPLETADO', 'EN_PROCESO'])
    
    if fecha_desde:
        ventas = ventas.filter(fecha_creacion__date__gte=fecha_desde)
    if fecha_hasta:
        ventas = ventas.filter(fecha_creacion__date__lte=fecha_hasta)
    if vendedor_id:
        ventas = ventas.filter(creado_por_id=vendedor_id)
    if plan_id:
        ventas = ventas.filter(plan_contratado_id=plan_id)
    if busqueda:
        ventas = ventas.filter(
            Q(cliente_potencial__nombre__icontains=busqueda) |
            Q(cliente_potencial__apellido__icontains=busqueda) |
            Q(cliente_potencial__cedula__icontains=busqueda) |
            Q(customer_id__icontains=busqueda)
        )
    
    total_registros = ventas.count()
    paginator = Paginator(ventas, per_page)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    if tipo_reporte == 'simple':
        # Reporte simple: Cliente, Customer ID, ODS, Fecha, Vendedor, Estado
        data_list = [{
            'id': v.id,
            'cliente': v.nombre_completo,
            'customer_id': v.customer_id or 'N/A',
            'ods': v.ods or 'N/A',
            'fecha': v.fecha_creacion.strftime('%d/%m/%Y'),
            'vendedor': v.creado_por.get_full_name() or v.creado_por.username if v.creado_por else 'N/A',
            'estado': v.get_estado_display(),
        } for v in page_obj]
    else:
        # Reporte avanzado: más campos
        data_list = [{
            'id': v.id,
            'cliente': v.nombre_completo,
            'cedula': v.cedula,
            'telefono': v.telefono_principal,
            'correo': v.correo_electronico,
            'direccion': v.direccion_detallada[:100] if v.direccion_detallada else 'N/A',
            'plan': v.plan_contratado.nombre,
            'fecha': v.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            'vendedor': v.creado_por.get_full_name() or v.creado_por.username if v.creado_por else 'N/A',
            'customer_id': v.customer_id or 'N/A',
            'ods': v.ods or 'N/A',
            'atr': v.atr or 'N/A',
            'estado': v.get_estado_display(),
        } for v in page_obj]
    
    estadisticas = {
        'total_ventas': total_registros,
        'completados': ventas.filter(estado='COMPLETADO').count(),
        'pendientes': ventas.filter(estado='EN_PROCESO').count(),
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
@user_passes_test(es_admin)
def reporte_instalaciones_json(request):
    """API para obtener datos de instalaciones"""
    
    tipo_reporte = request.GET.get('tipo', 'simple')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    cuadrilla_id = request.GET.get('cuadrilla', '')
    estado = request.GET.get('estado', '')
    busqueda = request.GET.get('busqueda', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 15))
    
    instalaciones = Instalacion.objects.select_related('asignacion__cuadrilla', 'asignacion__contrato', 'asignacion__venta_directa', 'modelo_modem')
    
    if fecha_desde:
        instalaciones = instalaciones.filter(fecha_instalacion__date__gte=fecha_desde)
    if fecha_hasta:
        instalaciones = instalaciones.filter(fecha_instalacion__date__lte=fecha_hasta)
    if cuadrilla_id:
        instalaciones = instalaciones.filter(asignacion__cuadrilla_id=cuadrilla_id)
    if estado == 'completada':
        instalaciones = instalaciones.filter(completada=True)
    elif estado == 'pendiente':
        instalaciones = instalaciones.filter(completada=False)
    
    # Búsqueda - usar los campos reales de la base de datos
    if busqueda:
        # Creamos una lista de IDs que coinciden con la búsqueda
        ids_coincidentes = []
        for inst in instalaciones:
            # Obtener datos a través de las propiedades
            nombre_cliente = inst.nombre_cliente
            cedula_cliente = inst.cedula_cliente
            customer_id = inst.customer_id
            
            if (busqueda.lower() in nombre_cliente.lower() or 
                busqueda.lower() in cedula_cliente.lower() or 
                (customer_id and busqueda.lower() in customer_id.lower())):
                ids_coincidentes.append(inst.id)
        
        instalaciones = instalaciones.filter(id__in=ids_coincidentes)
    
    total_registros = instalaciones.count()
    paginator = Paginator(instalaciones, per_page)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    if tipo_reporte == 'simple':
        # Reporte simple: Cliente, Customer ID, ODS, Fecha, Cuadrilla, Estado
        data_list = []
        for inst in page_obj:
            data_list.append({
                'id': inst.id,
                'cliente': inst.nombre_cliente,
                'customer_id': inst.customer_id,
                'ods': inst.orden_servicio,
                'fecha': inst.fecha_instalacion.strftime('%d/%m/%Y') if inst.fecha_instalacion else 'No registrada',
                'cuadrilla': inst.asignacion.cuadrilla.nombre if inst.asignacion and inst.asignacion.cuadrilla else 'N/A',
                'estado': 'Completada' if inst.completada else 'Pendiente',
            })
    else:
        # Reporte avanzado
        data_list = []
        for inst in page_obj:
            direccion = "N/A"
            try:
                if inst.asignacion and inst.asignacion.contrato:
                    direccion = inst.asignacion.contrato.direccion_detallada or "N/A"
                elif inst.asignacion and inst.asignacion.venta_directa:
                    direccion = getattr(inst.asignacion.venta_directa, 'direccion', None) or "N/A"
            except:
                direccion = "N/A"
            
            data_list.append({
                'id': inst.id,
                'cliente': inst.nombre_cliente,
                'cedula': inst.cedula_cliente,
                'direccion': direccion[:100] if direccion else 'N/A',
                'plan': inst.plan,
                'cuadrilla': inst.asignacion.cuadrilla.nombre if inst.asignacion and inst.asignacion.cuadrilla else 'N/A',
                'fecha': inst.fecha_instalacion.strftime('%d/%m/%Y %H:%M') if inst.fecha_instalacion else 'No registrada',
                'estado': 'Completada' if inst.completada else 'Pendiente',
                'modelo': inst.modelo_modem.nombre if inst.modelo_modem else 'N/A',
                'serial': inst.sn_modem or 'N/A',
                'metros': inst.metros_utilizados,
                'customer_id': inst.customer_id,
                'ods': inst.orden_servicio,
            })
    
    estadisticas = {
        'total_instalaciones': total_registros,
        'completadas': instalaciones.filter(completada=True).count(),
        'pendientes': instalaciones.filter(completada=False).count(),
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
@user_passes_test(es_admin)
def reporte_soportes_json(request):
    """API para obtener datos de soportes"""
    
    tipo_reporte = request.GET.get('tipo', 'simple')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    tipo_soporte = request.GET.get('tipo_soporte', '')
    estado = request.GET.get('estado', '')
    busqueda = request.GET.get('busqueda', '')
    cuadrilla_id = request.GET.get('cuadrilla', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 15))
    
    soportes = Soporte.objects.all()
    
    if fecha_desde:
        soportes = soportes.filter(fecha_hora_servicio__date__gte=fecha_desde)
    if fecha_hasta:
        soportes = soportes.filter(fecha_hora_servicio__date__lte=fecha_hasta)
    if estado:
        soportes = soportes.filter(estado=estado)
    if cuadrilla_id:
        soportes = soportes.filter(cuadrilla_id=cuadrilla_id)
    if tipo_soporte:
        soportes = soportes.filter(asignacion__ticket__tipo_soporte=tipo_soporte)
    if busqueda:
        soportes = soportes.filter(
            Q(asignacion__ticket__nombre__icontains=busqueda) |
            Q(asignacion__ticket__apellido__icontains=busqueda) |
            Q(asignacion__ticket__cedula__icontains=busqueda) |
            Q(asignacion__ticket__ticket_padre__icontains=busqueda)
        )
    
    total_registros = soportes.count()
    paginator = Paginator(soportes, per_page)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    if tipo_reporte == 'simple':
        data_list = []
        for s in page_obj:
            try:
                cliente_nombre = s.asignacion.ticket.nombre_completo if s.asignacion and s.asignacion.ticket else "N/A"
                cedula = s.asignacion.ticket.cedula if s.asignacion and s.asignacion.ticket else "N/A"
                customer_id = s.asignacion.ticket.customer_id if s.asignacion and s.asignacion.ticket else "N/A"
                ticket_padre = s.asignacion.ticket.ticket_padre if s.asignacion and s.asignacion.ticket else "N/A"
            except:
                cliente_nombre = "N/A"
                cedula = "N/A"
                customer_id = "N/A"
                ticket_padre = "N/A"
            
            data_list.append({
                'id': s.id,
                'cliente': cliente_nombre,
                'customer_id': customer_id,
                'ticket_padre': ticket_padre,
                'fecha': s.fecha_hora_servicio.strftime('%d/%m/%Y') if s.fecha_hora_servicio else s.fecha_creacion.strftime('%d/%m/%Y'),
                'cuadrilla': s.cuadrilla.nombre if s.cuadrilla else 'N/A',
                'estado': s.get_estado_display() if hasattr(s, 'get_estado_display') else s.estado,
            })
    else:
        data_list = []
        for s in page_obj:
            try:
                cliente_nombre = s.asignacion.ticket.nombre_completo if s.asignacion and s.asignacion.ticket else "N/A"
                cedula = s.asignacion.ticket.cedula if s.asignacion and s.asignacion.ticket else "N/A"
                ticket_padre = s.asignacion.ticket.ticket_padre if s.asignacion and s.asignacion.ticket else "N/A"
                tipo_display = s.asignacion.ticket.get_tipo_soporte_display() if s.asignacion and s.asignacion.ticket else "N/A"
            except:
                cliente_nombre = "N/A"
                cedula = "N/A"
                ticket_padre = "N/A"
                tipo_display = "N/A"
            
            data_list.append({
                'id': s.id,
                'ticket_padre': ticket_padre,
                'cliente': cliente_nombre,
                'cedula': cedula,
                'tipo': tipo_display,
                'estado': s.get_estado_display() if hasattr(s, 'get_estado_display') else s.estado,
                'fecha': s.fecha_hora_servicio.strftime('%d/%m/%Y %H:%M') if s.fecha_hora_servicio else s.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                'falla': s.falla_encontrada[:100] if s.falla_encontrada else 'N/A',
                'solucion': s.solucion[:100] if s.solucion else 'N/A',
                'cuadrilla': s.cuadrilla.nombre if s.cuadrilla else 'N/A',
                'instaladores': [inst.get_full_name() or inst.username for inst in s.instaladores.all()[:3]],
            })
    
    estadisticas = {
        'total_soportes': total_registros,
        'completados': soportes.filter(estado='COMPLETADO').count(),
        'pendientes': soportes.filter(estado='PENDIENTE').count(),
        'en_proceso': soportes.filter(estado='EN_PROCESO').count(),
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
@user_passes_test(es_admin)
def reporte_inventario_json(request):
    """API para obtener datos del inventario global"""
    
    tipo_reporte = request.GET.get('tipo', 'simple')
    material_id = request.GET.get('material', '')
    busqueda = request.GET.get('busqueda', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 15))
    
    inventario = InventarioGlobal.objects.select_related('material', 'actualizado_por')
    
    if material_id:
        inventario = inventario.filter(material_id=material_id)
    if busqueda:
        inventario = inventario.filter(material__nombre__icontains=busqueda)
    
    total_registros = inventario.count()
    paginator = Paginator(inventario, per_page)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    if tipo_reporte == 'simple':
        data_list = [{
            'id': item.id,
            'material': item.material.nombre,
            'cantidad': item.cantidad,
            'minimo': item.cantidad_minima,
            'estado': 'Bajo stock' if item.esta_bajo_stock else 'Normal',
        } for item in page_obj]
    else:
        data_list = [{
            'id': item.id,
            'material': item.material.nombre,
            'cantidad': item.cantidad,
            'minimo': item.cantidad_minima,
            'estado': 'Bajo stock' if item.esta_bajo_stock else 'Normal',
            'ultima_actualizacion': item.ultima_actualizacion.strftime('%d/%m/%Y %H:%M'),
            'actualizado_por': item.actualizado_por.get_full_name() or item.actualizado_por.username if item.actualizado_por else 'Sistema',
        } for item in page_obj]
    
    estadisticas = {
        'total_materiales': total_registros,
        'total_unidades': sum(item.cantidad for item in inventario),
        'bajo_stock': sum(1 for item in inventario if item.esta_bajo_stock),
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
@user_passes_test(es_admin)
def reporte_vendedores_json(request):
    """
    API para obtener reporte de vendedores con contratos completados
    por semana (viernes a jueves)
    """
    
    from decimal import Decimal
    
    # Obtener parámetros
    semana_fecha = request.GET.get('semana', '')
    vendedor_id = request.GET.get('vendedor', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 15))
    busqueda = request.GET.get('busqueda', '')
    
    # Calcular semana (viernes a jueves)
    if semana_fecha:
        try:
            fecha_referencia = datetime.strptime(semana_fecha, '%Y-%m-%d').date()
        except:
            fecha_referencia = datetime.now().date()
    else:
        fecha_referencia = datetime.now().date()
    
    dias_desde_viernes = fecha_referencia.weekday() - 4
    if dias_desde_viernes < 0:
        dias_desde_viernes += 7
    
    viernes_inicio = fecha_referencia - timedelta(days=dias_desde_viernes)
    jueves_fin = viernes_inicio + timedelta(days=6)
    
    # ===== LÓGICA SIMPLIFICADA =====
    # Usar fecha_completado directamente (mucho más simple y preciso)
    contratos = ContratoCliente.objects.filter(
        estado='COMPLETADO',
        fecha_completado__date__gte=viernes_inicio,
        fecha_completado__date__lte=jueves_fin
    )
    
    # Filtrar por vendedor
    if vendedor_id:
        contratos = contratos.filter(creado_por_id=vendedor_id)
    
    # Obtener todos los vendedores
    todos_vendedores = User.objects.filter(
        groups__name__in=['Vendedor', 'Supervisor']
    ).distinct().order_by('first_name', 'username')
    
    if vendedor_id:
        todos_vendedores = todos_vendedores.filter(id=vendedor_id)
    
    if busqueda:
        todos_vendedores = todos_vendedores.filter(
            Q(first_name__icontains=busqueda) |
            Q(username__icontains=busqueda) |
            Q(last_name__icontains=busqueda)
        )
    
    # Obtener tasa de cambio
    tasa_obj = TasaCambio.objects.filter(activo=True).first()
    if tasa_obj:
        tasa = float(tasa_obj.tasa)
        tasa_decimal = tasa_obj.tasa
    else:
        tasa = 0
        tasa_decimal = Decimal('0')
    
    vendedores_data = []
    
    for vendedor in todos_vendedores:
        # Contratos completados en esta semana para este vendedor
        contratos_vendedor = contratos.filter(creado_por=vendedor)
        total_contratos = contratos_vendedor.count()
        
        # Mostrar vendedor si tiene contratos o es el seleccionado
        if total_contratos > 0 or not vendedor_id:
            # Calcular comisión según rangos
            if total_contratos >= 1 and total_contratos <= 5:
                comision_por_contrato = 8
                bono = 20
                total_precio = total_contratos * 8
                rango = "1-5 contratos"
            elif total_contratos >= 6 and total_contratos <= 10:
                comision_por_contrato = 10
                bono = 40
                total_precio = total_contratos * 10
                rango = "6-10 contratos"
            elif total_contratos >= 11:
                comision_por_contrato = 10
                bono = 60
                total_precio = total_contratos * 10
                rango = "11+ contratos"
            else:
                comision_por_contrato = 0
                bono = 0
                total_precio = 0
                rango = "Sin contratos"
            
            total_con_bono = total_precio + bono
            total_bs = total_con_bono * tasa
            
            # Detalle de contratos (mostrar fecha_completado real)
            lista_contratos = []
            for contrato in contratos_vendedor.order_by('-fecha_completado')[:5]:
                lista_contratos.append({
                    'id': contrato.id,
                    'cliente': contrato.nombre_completo,
                    'fecha_completado': contrato.fecha_completado.strftime('%d/%m/%Y %H:%M') if contrato.fecha_completado else 'N/A',
                    'fecha_creacion': contrato.fecha_creacion.strftime('%d/%m/%Y'),
                    'plan': contrato.plan_contratado.nombre,
                    'customer_id': contrato.customer_id or 'N/A'
                })
            
            vendedores_data.append({
                'id': vendedor.id,
                'vendedor': vendedor.get_full_name() or vendedor.username,
                'username': vendedor.username,
                'contratos': total_contratos,
                'comision_por_contrato': f"${comision_por_contrato}",
                'total_sin_bono': f"${total_precio}",
                'bono': f"${bono}",
                'total_con_bono': f"${total_con_bono}",
                'total_bs': f"Bs {total_bs:,.2f}",
                'rango': rango,
                'contratos_detalle': lista_contratos
            })
    
    # Ordenar por cantidad de contratos (mayor a menor)
    vendedores_data.sort(key=lambda x: int(x['contratos']), reverse=True)
    
    # Paginación
    total_registros = len(vendedores_data)
    paginator = Paginator(vendedores_data, per_page)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    # Estadísticas
    total_contratos_semana = sum(v['contratos'] for v in vendedores_data)
    total_pagar_usd = sum(float(v['total_con_bono'].replace('$', '')) for v in vendedores_data)
    total_pagar_bs = total_pagar_usd * tasa
    
    fecha_tasa = tasa_obj.fecha.strftime('%d/%m/%Y') if tasa_obj else 'No definida'
    tasa_str = f"{float(tasa_decimal):,.2f}" if tasa_decimal else "0.00"
    
    estadisticas = {
        'total_vendedores': len(vendedores_data),
        'total_contratos_semana': total_contratos_semana,
        'total_pagar_usd': f"${total_pagar_usd:,.2f}",
        'total_pagar_bs': f"Bs {total_pagar_bs:,.2f}",
        'semana_inicio': viernes_inicio.strftime('%d/%m/%Y'),
        'semana_fin': jueves_fin.strftime('%d/%m/%Y'),
        'tasa_cambio': f"1 USD = {tasa_str} Bs",
        'fecha_actualizacion_tasa': fecha_tasa
    }
    
    return JsonResponse({
        'data': list(page_obj),
        'estadisticas': estadisticas,
        'total_registros': total_registros,
        'total_paginas': paginator.num_pages,
        'pagina_actual': page_obj.number,
        'por_pagina': per_page,
        'semana_inicio': viernes_inicio.strftime('%Y-%m-%d'),
        'semana_fin': jueves_fin.strftime('%Y-%m-%d')
    })




@staff_member_required
@csrf_exempt
def api_actualizar_tasa(request):
    """API para actualizar la tasa de cambio manualmente"""
    if request.method == 'POST':
        try:
            # Ejecutar el comando
            call_command('actualizar_tasa')
            return JsonResponse({
                'success': True,
                'message': 'Tasa actualizada correctamente'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            }, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required
@user_passes_test(es_admin)
def semanas_disponibles_api(request):
    """API para obtener las semanas disponibles con contratos completados"""
    
    # Obtener todas las semanas donde hay contratos completados
    contratos = ContratoCliente.objects.filter(estado='COMPLETADO').order_by('fecha_creacion')
    
    semanas = []
    fechas_procesadas = set()
    
    for contrato in contratos:
        fecha = contrato.fecha_creacion.date()
        
        # Calcular semana (viernes a jueves)
        dias_desde_viernes = fecha.weekday() - 4
        if dias_desde_viernes < 0:
            dias_desde_viernes += 7
        
        viernes_inicio = fecha - timedelta(days=dias_desde_viernes)
        jueves_fin = viernes_inicio + timedelta(days=6)
        
        clave = viernes_inicio.strftime('%Y-%m-%d')
        
        if clave not in fechas_procesadas:
            fechas_procesadas.add(clave)
            semanas.append({
                'value': viernes_inicio.strftime('%Y-%m-%d'),
                'label': f"{viernes_inicio.strftime('%d/%m/%Y')} - {jueves_fin.strftime('%d/%m/%Y')}"
            })
    
    # Ordenar por fecha descendente
    semanas.sort(key=lambda x: x['value'], reverse=True)
    
    # Agregar semana actual
    hoy = datetime.now().date()
    dias_desde_viernes = hoy.weekday() - 4
    if dias_desde_viernes < 0:
        dias_desde_viernes += 7
    
    viernes_actual = hoy - timedelta(days=dias_desde_viernes)
    jueves_actual = viernes_actual + timedelta(days=6)
    semana_actual_clave = viernes_actual.strftime('%Y-%m-%d')
    
    semana_actual = {
        'value': semana_actual_clave,
        'label': f"Semana Actual ({viernes_actual.strftime('%d/%m/%Y')} - {jueves_actual.strftime('%d/%m/%Y')})"
    }
    
    # Verificar si la semana actual ya está en la lista
    if not any(s['value'] == semana_actual_clave for s in semanas):
        semanas.insert(0, semana_actual)
    
    return JsonResponse({'semanas': semanas})


@login_required
@user_passes_test(es_admin)
def reporte_instaladores_json(request):
    """
    API para obtener reporte de CUADRILLAS para PAGO DE NÓMINA:
    - Instalaciones COMPLETADAS: $15 c/u (usando fecha_instalacion)
    - Soportes COMPLETADOS: según tipo (usando fecha_creacion)
    - Contratos (ventas): $10 c/u - por contratos COMPLETADOS creados por instaladores
    Por semana (viernes a jueves)
    """
    
    from decimal import Decimal
    from collections import defaultdict
    
    # Obtener parámetros
    semana_fecha = request.GET.get('semana', '')
    instalador_id = request.GET.get('instalador', '')
    cuadrilla_id = request.GET.get('cuadrilla', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 15))
    busqueda = request.GET.get('busqueda', '')
    
    # Calcular semana (viernes a jueves)
    if semana_fecha:
        try:
            fecha_referencia = datetime.strptime(semana_fecha, '%Y-%m-%d').date()
        except:
            fecha_referencia = datetime.now().date()
    else:
        fecha_referencia = datetime.now().date()
    
    dias_desde_viernes = fecha_referencia.weekday() - 4
    if dias_desde_viernes < 0:
        dias_desde_viernes += 7
    
    viernes_inicio = fecha_referencia - timedelta(days=dias_desde_viernes)
    jueves_fin = viernes_inicio + timedelta(days=6)
    
    # Precios
    PRECIO_INSTALACION = 15
    PRECIO_CONTRATO = 10
    PRECIOS_SOPORTES = {
        'SOPORTE': 10,
        'RETIRO': 8,
        'MUDANZA': 15,
        'RECABLEADO': 15,
    }
    
    # Obtener todas las cuadrillas activas
    todas_cuadrillas = Cuadrilla.objects.filter(activo=True)
    
    # Filtrar por cuadrilla si se especifica
    if cuadrilla_id:
        todas_cuadrillas = todas_cuadrillas.filter(id=cuadrilla_id)
    
    # ===== DICCIONARIO PARA AGRUPAR POR CUADRILLA =====
    cuadrillas_dict = defaultdict(lambda: {
        'id': None,
        'cuadrilla': '',
        'instalaciones': 0,
        'monto_instalaciones': 0,
        'soportes': 0,
        'monto_soportes': 0,
        'contratos': 0,
        'monto_contratos': 0,
        'instaladores_set': set(),
        'instalaciones_detalle': [],
        'soportes_detalle': [],
        'contratos_detalle': []
    })
    
    # Primero, registrar todas las cuadrillas en el diccionario
    for cuadrilla in todas_cuadrillas:
        cuadrillas_dict[cuadrilla.nombre]['id'] = cuadrilla.id
        cuadrillas_dict[cuadrilla.nombre]['cuadrilla'] = cuadrilla.nombre
        
        # Obtener los instaladores de esta cuadrilla (a través de PerfilUsuario)
        perfiles = cuadrilla.instaladores.all()
        for perfil in perfiles:
            if perfil.usuario:
                cuadrillas_dict[cuadrilla.nombre]['instaladores_set'].add(perfil.usuario.id)
    
    # ========== 1. INSTALACIONES COMPLETADAS (para PAGO) ==========
    # Solo instalaciones COMPLETADAS en la semana (viernes a jueves)
    instalaciones = Instalacion.objects.filter(
        completada=True,
        fecha_instalacion__date__gte=viernes_inicio,
        fecha_instalacion__date__lte=jueves_fin
    ).select_related('asignacion__cuadrilla')
    
    for inst in instalaciones:
        cuadrilla_obj = inst.asignacion.cuadrilla if inst.asignacion else None
        if not cuadrilla_obj:
            continue
        
        nombre_cuadrilla = cuadrilla_obj.nombre
        if nombre_cuadrilla not in cuadrillas_dict:
            continue
        
        # Obtener instaladores históricos (para filtros y detalle)
        instaladores_hist = inst.instaladores.all()
        
        # Verificar filtro por instalador específico
        if instalador_id:
            if not instaladores_hist.filter(id=instalador_id).exists():
                continue
        
        # Verificar búsqueda
        if busqueda:
            tiene_coincidencia = False
            for inst_hist in instaladores_hist:
                nombre_completo = inst_hist.get_full_name() or inst_hist.username
                if busqueda.lower() in nombre_completo.lower():
                    tiene_coincidencia = True
                    break
            if not tiene_coincidencia:
                continue
        
        cuadrillas_dict[nombre_cuadrilla]['instalaciones'] += 1
        cuadrillas_dict[nombre_cuadrilla]['monto_instalaciones'] += PRECIO_INSTALACION
        
        for inst_hist in instaladores_hist:
            cuadrillas_dict[nombre_cuadrilla]['instaladores_set'].add(inst_hist.id)
        
        # Detalle
        if len(cuadrillas_dict[nombre_cuadrilla]['instalaciones_detalle']) < 5:
            cliente_nombre = inst.nombre_cliente if hasattr(inst, 'nombre_cliente') else 'N/A'
            customer_id = inst.customer_id if hasattr(inst, 'customer_id') else 'N/A'
            nombres_inst = [i.get_full_name() or i.username for i in instaladores_hist[:3]]
            cuadrillas_dict[nombre_cuadrilla]['instalaciones_detalle'].append({
                'cliente': cliente_nombre,
                'customer_id': customer_id,
                'fecha': inst.fecha_instalacion.strftime('%d/%m/%Y') if inst.fecha_instalacion else 'N/A',
                'instaladores': ', '.join(nombres_inst)
            })
    
    # ========== 2. SOPORTES COMPLETADOS ==========
    soportes = Soporte.objects.filter(
        estado='COMPLETADO',
        fecha_creacion__date__gte=viernes_inicio,
        fecha_creacion__date__lte=jueves_fin
    ).select_related('cuadrilla')
    
    for sop in soportes:
        if not sop.cuadrilla:
            continue
        
        nombre_cuadrilla = sop.cuadrilla.nombre
        if nombre_cuadrilla not in cuadrillas_dict:
            continue
        
        instaladores_hist = sop.instaladores.all()
        
        if instalador_id:
            if not instaladores_hist.filter(id=instalador_id).exists():
                continue
        
        if busqueda:
            tiene_coincidencia = False
            for inst_hist in instaladores_hist:
                nombre_completo = inst_hist.get_full_name() or inst_hist.username
                if busqueda.lower() in nombre_completo.lower():
                    tiene_coincidencia = True
                    break
            if not tiene_coincidencia:
                continue
        
        try:
            tipo = sop.asignacion.ticket.tipo_soporte if sop.asignacion and sop.asignacion.ticket else 'SOPORTE'
            precio = PRECIOS_SOPORTES.get(tipo, 10)
        except:
            precio = 10
            tipo = 'SOPORTE'
        
        cuadrillas_dict[nombre_cuadrilla]['soportes'] += 1
        cuadrillas_dict[nombre_cuadrilla]['monto_soportes'] += precio
        
        for inst_hist in instaladores_hist:
            cuadrillas_dict[nombre_cuadrilla]['instaladores_set'].add(inst_hist.id)
        
        if len(cuadrillas_dict[nombre_cuadrilla]['soportes_detalle']) < 5:
            cliente_nombre = 'N/A'
            try:
                if sop.asignacion and sop.asignacion.ticket:
                    cliente_nombre = sop.asignacion.ticket.nombre_completo
            except:
                pass
            nombres_inst = [i.get_full_name() or i.username for i in instaladores_hist[:3]]
            cuadrillas_dict[nombre_cuadrilla]['soportes_detalle'].append({
                'ticket_padre': sop.asignacion.ticket.ticket_padre if sop.asignacion and sop.asignacion.ticket else 'N/A',
                'cliente': cliente_nombre,
                'tipo': tipo,
                'precio': precio,
                'fecha': sop.fecha_creacion.strftime('%d/%m/%Y') if sop.fecha_creacion else 'N/A',
                'instaladores': ', '.join(nombres_inst)
            })
    
    # ========== 3. CONTRATOS COMPLETADOS (creados por INSTALADORES) ==========
    instaladores_users = User.objects.filter(groups__name='Instalador')
    
    if instalador_id:
        instaladores_users = instaladores_users.filter(id=instalador_id)
    
    for instalador in instaladores_users:
        perfil = PerfilUsuario.objects.filter(usuario=instalador).first()
        if not perfil:
            continue
        
        cuadrillas_del_instalador = perfil.cuadrillas.all()
        if not cuadrillas_del_instalador.exists():
            continue
        
        contratos_instalador = ContratoCliente.objects.filter(
            estado='COMPLETADO',
            creado_por=instalador,
            fecha_completado__date__gte=viernes_inicio,
            fecha_completado__date__lte=jueves_fin
        )
        
        if busqueda:
            contratos_instalador = contratos_instalador.filter(
                Q(cliente_potencial__nombre__icontains=busqueda) |
                Q(cliente_potencial__apellido__icontains=busqueda) |
                Q(cliente_potencial__cedula__icontains=busqueda) |
                Q(customer_id__icontains=busqueda)
            )
        
        for contrato in contratos_instalador:
            for cuadrilla_inst in cuadrillas_del_instalador:
                nombre_cuadrilla = cuadrilla_inst.nombre
                if nombre_cuadrilla not in cuadrillas_dict:
                    continue
                
                if cuadrilla_id and int(cuadrilla_id) != cuadrillas_dict[nombre_cuadrilla]['id']:
                    continue
                
                cuadrillas_dict[nombre_cuadrilla]['contratos'] += 1
                cuadrillas_dict[nombre_cuadrilla]['monto_contratos'] += PRECIO_CONTRATO
                cuadrillas_dict[nombre_cuadrilla]['instaladores_set'].add(instalador.id)
                
                if len(cuadrillas_dict[nombre_cuadrilla]['contratos_detalle']) < 5:
                    cuadrillas_dict[nombre_cuadrilla]['contratos_detalle'].append({
                        'cliente': contrato.nombre_completo,
                        'plan': contrato.plan_contratado.nombre,
                        'customer_id': contrato.customer_id or 'N/A',
                        'fecha_completado': contrato.fecha_completado.strftime('%d/%m/%Y') if contrato.fecha_completado else 'N/A'
                    })
    
    # ===== CONSTRUIR LISTA FINAL =====
    cuadrillas_data = []
    for nombre, data in cuadrillas_dict.items():
        total_usd = data['monto_instalaciones'] + data['monto_soportes'] + data['monto_contratos']
        
        nombres_instaladores = []
        for inst_id in data['instaladores_set']:
            try:
                inst = User.objects.get(id=inst_id)
                nombres_instaladores.append(inst.get_full_name() or inst.username)
            except:
                pass
        
        if (data['instalaciones'] > 0 or data['soportes'] > 0 or data['contratos'] > 0 or cuadrilla_id):
            cuadrillas_data.append({
                'id': data['id'],
                'cuadrilla': data['cuadrilla'],
                'instalaciones': data['instalaciones'],
                'monto_instalaciones': f"${data['monto_instalaciones']}",
                'soportes': data['soportes'],
                'monto_soportes': f"${data['monto_soportes']}",
                'contratos': data['contratos'],
                'monto_contratos': f"${data['monto_contratos']}",
                'total_usd': f"${total_usd}",
                'instaladores_list': nombres_instaladores,
                'instalaciones_detalle': data['instalaciones_detalle'],
                'soportes_detalle': data['soportes_detalle'],
                'contratos_detalle': data['contratos_detalle'],
            })
    
    cuadrillas_data.sort(key=lambda x: x['instalaciones'] + x['soportes'] + x['contratos'], reverse=True)
    
    tasa_obj = TasaCambio.objects.filter(activo=True).first()
    if tasa_obj:
        tasa = float(tasa_obj.tasa)
        tasa_decimal = tasa_obj.tasa
    else:
        tasa = 0
        tasa_decimal = Decimal('0')
    
    for item in cuadrillas_data:
        total_usd_num = float(item['total_usd'].replace('$', ''))
        item['total_bs'] = f"Bs {total_usd_num * tasa:,.2f}"
    
    total_registros = len(cuadrillas_data)
    paginator = Paginator(cuadrillas_data, per_page)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    total_instalaciones_semana = sum(v['instalaciones'] for v in cuadrillas_data)
    total_soportes_semana = sum(v['soportes'] for v in cuadrillas_data)
    total_contratos_semana = sum(v['contratos'] for v in cuadrillas_data)
    total_pagar_usd = sum(float(v['total_usd'].replace('$', '')) for v in cuadrillas_data)
    total_pagar_bs = total_pagar_usd * tasa
    
    fecha_tasa = tasa_obj.fecha.strftime('%d/%m/%Y') if tasa_obj else 'No definida'
    tasa_str = f"{float(tasa_decimal):,.2f}" if tasa_decimal else "0.00"
    
    estadisticas = {
        'total_cuadrillas': len(cuadrillas_data),
        'total_instalaciones_semana': total_instalaciones_semana,
        'total_soportes_semana': total_soportes_semana,
        'total_contratos_semana': total_contratos_semana,
        'total_pagar_usd': f"${total_pagar_usd:,.2f}",
        'total_pagar_bs': f"Bs {total_pagar_bs:,.2f}",
        'semana_inicio': viernes_inicio.strftime('%d/%m/%Y'),
        'semana_fin': jueves_fin.strftime('%d/%m/%Y'),
        'tasa_cambio': f"1 USD = {tasa_str} Bs",
        'fecha_actualizacion_tasa': fecha_tasa,
        'precio_instalacion': f"${PRECIO_INSTALACION}",
        'precio_contrato': f"${PRECIO_CONTRATO}",
    }
    
    return JsonResponse({
        'data': list(page_obj),
        'estadisticas': estadisticas,
        'total_registros': total_registros,
        'total_paginas': paginator.num_pages,
        'pagina_actual': page_obj.number,
        'por_pagina': per_page,
        'semana_inicio': viernes_inicio.strftime('%Y-%m-%d'),
        'semana_fin': jueves_fin.strftime('%Y-%m-%d')
    })
    
    
@login_required
@user_passes_test(es_admin)
def semanas_disponibles_instaladores_api(request):
    """API para obtener las semanas disponibles con actividad de instaladores"""
    
    from datetime import timedelta
    
    # Obtener fechas de instalaciones, soportes y contratos
    fechas = []
    
    # Instalaciones
    instalaciones = Instalacion.objects.filter(completada=True).exclude(fecha_instalacion__isnull=True)
    for inst in instalaciones:
        if inst.fecha_instalacion:
            fechas.append(inst.fecha_instalacion.date())
    
    # Soportes
    soportes = Soporte.objects.filter(estado='COMPLETADO').exclude(fecha_hora_servicio__isnull=True)
    for sop in soportes:
        if sop.fecha_hora_servicio:
            fechas.append(sop.fecha_hora_servicio.date())
    
    # Contratos completados
    contratos = ContratoCliente.objects.filter(estado='COMPLETADO').exclude(fecha_completado__isnull=True)
    for con in contratos:
        if con.fecha_completado:
            fechas.append(con.fecha_completado.date())
    
    semanas = []
    fechas_procesadas = set()
    
    for fecha in fechas:
        # Calcular semana (viernes a jueves)
        dias_desde_viernes = fecha.weekday() - 4
        if dias_desde_viernes < 0:
            dias_desde_viernes += 7
        
        viernes_inicio = fecha - timedelta(days=dias_desde_viernes)
        jueves_fin = viernes_inicio + timedelta(days=6)
        
        clave = viernes_inicio.strftime('%Y-%m-%d')
        
        if clave not in fechas_procesadas:
            fechas_procesadas.add(clave)
            semanas.append({
                'value': viernes_inicio.strftime('%Y-%m-%d'),
                'label': f"{viernes_inicio.strftime('%d/%m/%Y')} - {jueves_fin.strftime('%d/%m/%Y')}"
            })
    
    # Ordenar por fecha descendente
    semanas.sort(key=lambda x: x['value'], reverse=True)
    
    # Agregar semana actual
    hoy = datetime.now().date()
    dias_desde_viernes = hoy.weekday() - 4
    if dias_desde_viernes < 0:
        dias_desde_viernes += 7
    
    viernes_actual = hoy - timedelta(days=dias_desde_viernes)
    jueves_actual = viernes_actual + timedelta(days=6)
    semana_actual_clave = viernes_actual.strftime('%Y-%m-%d')
    
    semana_actual = {
        'value': semana_actual_clave,
        'label': f"Semana Actual ({viernes_actual.strftime('%d/%m/%Y')} - {jueves_actual.strftime('%d/%m/%Y')})"
    }
    
    if not any(s['value'] == semana_actual_clave for s in semanas):
        semanas.insert(0, semana_actual)
    
    return JsonResponse({'semanas': semanas})    



@login_required
@user_passes_test(es_admin)
def exportar_reporte(request):
    """Exportar datos a Excel o PDF"""
    
    formato = request.GET.get('formato', 'excel')
    tipo = request.GET.get('tipo', 'ventas')
    reporte_tipo = request.GET.get('reporte_tipo', 'simple')
    
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    busqueda = request.GET.get('busqueda', '')
    
    vendedor = request.GET.get('vendedor', '')
    plan = request.GET.get('plan', '')
    cuadrilla = request.GET.get('cuadrilla', '')
    estado = request.GET.get('estado', '')
    tipo_soporte = request.GET.get('tipo_soporte', '')
    estado_soporte = request.GET.get('estado_soporte', '')
    material = request.GET.get('material', '')
    semana = request.GET.get('semana', '')
    instalador = request.GET.get('instalador', '')  # Para reporte de instaladores
    
    if formato == 'excel':
        return exportar_excel(request, tipo, reporte_tipo, fecha_desde, fecha_hasta, 
                              busqueda, vendedor, plan, cuadrilla, estado, 
                              tipo_soporte, estado_soporte, material, semana, instalador)
    else:
        return exportar_pdf(request, tipo, reporte_tipo, fecha_desde, fecha_hasta,
                            busqueda, vendedor, plan, cuadrilla, estado,
                            tipo_soporte, estado_soporte, material, semana, instalador)


def exportar_excel(request, tipo, reporte_tipo, fecha_desde, fecha_hasta,
                   busqueda, vendedor, plan, cuadrilla, estado,
                   tipo_soporte, estado_soporte, material, semana, instalador):
    """Exportar datos a Excel con filtros"""
    
    wb = Workbook()
    
    if tipo == 'ventas':
        ws = wb.active
        ws.title = "Reporte de Ventas"
        
        # Incluir COMPLETADO y EN_PROCESO
        ventas = ContratoCliente.objects.filter(estado__in=['COMPLETADO', 'EN_PROCESO'])
        
        if fecha_desde:
            ventas = ventas.filter(fecha_creacion__date__gte=fecha_desde)
        if fecha_hasta:
            ventas = ventas.filter(fecha_creacion__date__lte=fecha_hasta)
        if vendedor:
            ventas = ventas.filter(creado_por_id=vendedor)
        if plan:
            ventas = ventas.filter(plan_contratado_id=plan)
        if busqueda:
            ventas = ventas.filter(
                Q(cliente_potencial__nombre__icontains=busqueda) |
                Q(cliente_potencial__apellido__icontains=busqueda) |
                Q(cliente_potencial__cedula__icontains=busqueda) |
                Q(customer_id__icontains=busqueda)
            )
        
        ventas = ventas.order_by('-fecha_creacion')
        
        if reporte_tipo == 'simple':
            headers = ['Cliente', 'Customer ID', 'ODS', 'Fecha', 'Vendedor', 'Estado']
            data = [[
                v.nombre_completo,
                v.customer_id or 'N/A',
                v.ods or 'N/A',
                v.fecha_creacion.strftime('%d/%m/%Y'),
                v.creado_por.get_full_name() or v.creado_por.username if v.creado_por else 'N/A',
                v.get_estado_display()
            ] for v in ventas]
        else:
            headers = ['ID', 'Cliente', 'Cédula', 'Teléfono', 'Correo', 'Dirección', 'Plan', 'Fecha', 'Vendedor', 'Customer ID', 'ODS', 'ATR', 'Estado']
            data = [[
                v.id,
                v.nombre_completo,
                v.cedula,
                v.telefono_principal,
                v.correo_electronico,
                v.direccion_detallada[:100] if v.direccion_detallada else 'N/A',
                v.plan_contratado.nombre,
                v.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                v.creado_por.get_full_name() or v.creado_por.username if v.creado_por else 'N/A',
                v.customer_id or 'N/A',
                v.ods or 'N/A',
                v.atr or 'N/A',
                v.get_estado_display()
            ] for v in ventas]
        
        # Hoja de resumen
        ws_resumen = wb.create_sheet("Resumen")
        total_registros = ventas.count()
        completados = ventas.filter(estado='COMPLETADO').count()
        en_proceso = ventas.filter(estado='EN_PROCESO').count()
        
        resumen_data = [
            ['REPORTE DE VENTAS', ''],
            ['', ''],
            ['Fecha de generación:', datetime.now().strftime('%d/%m/%Y %H:%M:%S')],
            ['', ''],
            ['ESTADÍSTICAS:', ''],
            ['Total de contratos:', total_registros],
            ['Completados:', completados],
            ['En proceso:', en_proceso],
        ]
        
        for row_idx, row_data in enumerate(resumen_data, 1):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws_resumen.cell(row=row_idx, column=col_idx, value=value)
                if row_idx == 1:
                    cell.font = Font(bold=True, size=14, color="FF6B00")
                elif row_idx == 5:
                    cell.font = Font(bold=True)
        
        ws_resumen.column_dimensions['A'].width = 25
        
    elif tipo == 'instalaciones':
        ws = wb.active
        ws.title = "Reporte de Instalaciones"
        
        instalaciones = Instalacion.objects.all()
        
        if fecha_desde:
            instalaciones = instalaciones.filter(fecha_instalacion__date__gte=fecha_desde)
        if fecha_hasta:
            instalaciones = instalaciones.filter(fecha_instalacion__date__lte=fecha_hasta)
        if cuadrilla:
            instalaciones = instalaciones.filter(asignacion__cuadrilla_id=cuadrilla)
        if estado == 'completada':
            instalaciones = instalaciones.filter(completada=True)
        elif estado == 'pendiente':
            instalaciones = instalaciones.filter(completada=False)
        if busqueda:
            instalaciones = instalaciones.filter(
                Q(nombre_cliente__icontains=busqueda) |
                Q(cedula_cliente__icontains=busqueda) |
                Q(customer_id__icontains=busqueda)
            )
        
        instalaciones = instalaciones.order_by('-fecha_instalacion')
        
        if reporte_tipo == 'simple':
            headers = ['Cliente', 'Customer ID', 'ODS', 'Fecha', 'Cuadrilla', 'Estado']
            data = []
            for i in instalaciones:
                data.append([
                    i.nombre_cliente,
                    i.customer_id,
                    i.orden_servicio,
                    i.fecha_instalacion.strftime('%d/%m/%Y') if i.fecha_instalacion else 'No registrada',
                    i.asignacion.cuadrilla.nombre if i.asignacion and i.asignacion.cuadrilla else 'N/A',
                    'Completada' if i.completada else 'Pendiente'
                ])
        else:
            headers = ['ID', 'Cliente', 'Cédula', 'Dirección', 'Plan', 'Cuadrilla', 'Fecha', 'Estado', 'Modelo', 'Serial', 'Metros', 'Customer ID', 'ODS']
            data = []
            for i in instalaciones:
                direccion = "N/A"
                try:
                    if i.asignacion and i.asignacion.contrato:
                        direccion = i.asignacion.contrato.direccion_detallada or "N/A"
                except:
                    pass
                
                data.append([
                    i.id,
                    i.nombre_cliente,
                    i.cedula_cliente,
                    direccion[:100] if direccion else 'N/A',
                    i.plan,
                    i.asignacion.cuadrilla.nombre if i.asignacion and i.asignacion.cuadrilla else 'N/A',
                    i.fecha_instalacion.strftime('%d/%m/%Y') if i.fecha_instalacion else 'No registrada',
                    'Completada' if i.completada else 'Pendiente',
                    i.modelo_modem.nombre if i.modelo_modem else 'N/A',
                    i.sn_modem or 'N/A',
                    i.metros_utilizados,
                    i.customer_id,
                    i.orden_servicio
                ])
        
    elif tipo == 'soportes':
        ws = wb.active
        ws.title = "Reporte de Soportes"
        
        soportes = Soporte.objects.all()
        
        if fecha_desde:
            soportes = soportes.filter(fecha_hora_servicio__date__gte=fecha_desde)
        if fecha_hasta:
            soportes = soportes.filter(fecha_hora_servicio__date__lte=fecha_hasta)
        if tipo_soporte:
            soportes = soportes.filter(asignacion__ticket__tipo_soporte=tipo_soporte)
        if estado_soporte:
            soportes = soportes.filter(estado=estado_soporte)
        if busqueda:
            soportes = soportes.filter(
                Q(asignacion__ticket__nombre__icontains=busqueda) |
                Q(asignacion__ticket__apellido__icontains=busqueda) |
                Q(asignacion__ticket__cedula__icontains=busqueda)
            )
        
        soportes = soportes.order_by('-fecha_hora_servicio', '-fecha_creacion')
        
        if reporte_tipo == 'simple':
            headers = ['Cliente', 'Customer ID', 'Ticket Padre', 'Fecha', 'Cuadrilla', 'Estado']
            data = []
            for s in soportes:
                try:
                    cliente = s.asignacion.ticket.nombre_completo if s.asignacion and s.asignacion.ticket else 'N/A'
                    customer_id = s.asignacion.ticket.customer_id if s.asignacion and s.asignacion.ticket else 'N/A'
                    ticket_padre = s.asignacion.ticket.ticket_padre if s.asignacion and s.asignacion.ticket else 'N/A'
                except:
                    cliente = 'N/A'
                    customer_id = 'N/A'
                    ticket_padre = 'N/A'
                
                data.append([
                    cliente,
                    customer_id,
                    ticket_padre,
                    s.fecha_hora_servicio.strftime('%d/%m/%Y') if s.fecha_hora_servicio else s.fecha_creacion.strftime('%d/%m/%Y'),
                    s.cuadrilla.nombre if s.cuadrilla else 'N/A',
                    s.get_estado_display() if hasattr(s, 'get_estado_display') else s.estado
                ])
        else:
            headers = ['ID', 'Ticket Padre', 'Cliente', 'Cédula', 'Tipo', 'Estado', 'Fecha', 'Falla', 'Solución', 'Cuadrilla']
            data = []
            for s in soportes:
                try:
                    ticket_padre = s.asignacion.ticket.ticket_padre if s.asignacion and s.asignacion.ticket else 'N/A'
                    cliente = s.asignacion.ticket.nombre_completo if s.asignacion and s.asignacion.ticket else 'N/A'
                    cedula = s.asignacion.ticket.cedula if s.asignacion and s.asignacion.ticket else 'N/A'
                    tipo_display = s.asignacion.ticket.get_tipo_soporte_display() if s.asignacion and s.asignacion.ticket else 'N/A'
                except:
                    ticket_padre = 'N/A'
                    cliente = 'N/A'
                    cedula = 'N/A'
                    tipo_display = 'N/A'
                
                data.append([
                    s.id,
                    ticket_padre,
                    cliente,
                    cedula,
                    tipo_display,
                    s.get_estado_display() if hasattr(s, 'get_estado_display') else s.estado,
                    s.fecha_hora_servicio.strftime('%d/%m/%Y') if s.fecha_hora_servicio else s.fecha_creacion.strftime('%d/%m/%Y'),
                    (s.falla_encontrada[:100] + '...') if s.falla_encontrada and len(s.falla_encontrada) > 100 else (s.falla_encontrada or 'N/A'),
                    (s.solucion[:100] + '...') if s.solucion and len(s.solucion) > 100 else (s.solucion or 'N/A'),
                    s.cuadrilla.nombre if s.cuadrilla else 'N/A'
                ])
        
    elif tipo == 'inventario':
        ws = wb.active
        ws.title = "Reporte de Inventario"
        
        inventario = InventarioGlobal.objects.select_related('material')
        
        if material:
            inventario = inventario.filter(material_id=material)
        if busqueda:
            inventario = inventario.filter(material__nombre__icontains=busqueda)
        
        inventario = inventario.order_by('material__nombre')
        
        if reporte_tipo == 'simple':
            headers = ['Material', 'Cantidad', 'Mínimo', 'Estado']
            data = [[
                item.material.nombre,
                item.cantidad,
                item.cantidad_minima,
                'Bajo stock' if item.esta_bajo_stock else 'Normal'
            ] for item in inventario]
        else:
            headers = ['ID', 'Material', 'Cantidad', 'Mínimo', 'Estado', 'Última Actualización', 'Actualizado Por']
            data = [[
                item.id,
                item.material.nombre,
                item.cantidad,
                item.cantidad_minima,
                'Bajo stock' if item.esta_bajo_stock else 'Normal',
                item.ultima_actualizacion.strftime('%d/%m/%Y %H:%M'),
                item.actualizado_por.get_full_name() or item.actualizado_por.username if item.actualizado_por else 'Sistema'
            ] for item in inventario]
    
    elif tipo == 'vendedores':
        ws = wb.active
        ws.title = "Reporte de Vendedores"
        
        from datetime import timedelta
        
        if semana:
            try:
                fecha_referencia = datetime.strptime(semana, '%Y-%m-%d').date()
            except:
                fecha_referencia = datetime.now().date()
        else:
            fecha_referencia = datetime.now().date()
        
        dias_desde_viernes = fecha_referencia.weekday() - 4
        if dias_desde_viernes < 0:
            dias_desde_viernes += 7
        
        viernes_inicio = fecha_referencia - timedelta(days=dias_desde_viernes)
        jueves_fin = viernes_inicio + timedelta(days=6)
        
        contratos = ContratoCliente.objects.filter(
            estado='COMPLETADO',
            fecha_completado__date__gte=viernes_inicio,
            fecha_completado__date__lte=jueves_fin
        )
        
        if vendedor:
            contratos = contratos.filter(creado_por_id=vendedor)
        
        vendedores = User.objects.filter(
            groups__name__in=['Vendedor', 'Supervisor']
        ).distinct()
        
        if vendedor:
            vendedores = vendedores.filter(id=vendedor)
        
        if busqueda:
            vendedores = vendedores.filter(
                Q(first_name__icontains=busqueda) |
                Q(username__icontains=busqueda) |
                Q(last_name__icontains=busqueda)
            )
        
        tasa_obj = TasaCambio.objects.filter(activo=True).first()
        tasa = float(tasa_obj.tasa) if tasa_obj else 0
        
        data_vendedores = []
        
        for vendedor_obj in vendedores:
            contratos_vendedor = contratos.filter(creado_por=vendedor_obj)
            total_contratos = contratos_vendedor.count()
            
            if total_contratos > 0 or not vendedor:
                if total_contratos >= 1 and total_contratos <= 5:
                    comision_por_contrato = 8
                    bono = 20
                    total_precio = total_contratos * 8
                    rango = "1-5 contratos"
                elif total_contratos >= 6 and total_contratos <= 10:
                    comision_por_contrato = 10
                    bono = 40
                    total_precio = total_contratos * 10
                    rango = "6-10 contratos"
                elif total_contratos >= 11:
                    comision_por_contrato = 10
                    bono = 60
                    total_precio = total_contratos * 10
                    rango = "11+ contratos"
                else:
                    comision_por_contrato = 0
                    bono = 0
                    total_precio = 0
                    rango = "Sin contratos"
                
                total_con_bono = total_precio + bono
                total_bs = total_con_bono * tasa
                
                data_vendedores.append({
                    'vendedor': vendedor_obj.get_full_name() or vendedor_obj.username,
                    'contratos': total_contratos,
                    'comision_por_contrato': comision_por_contrato,
                    'total_sin_bono': total_precio,
                    'bono': bono,
                    'total_con_bono': total_con_bono,
                    'total_bs': total_bs,
                    'rango': rango
                })
        
        data_vendedores.sort(key=lambda x: x['contratos'], reverse=True)
        
        total_contratos_general = sum(v['contratos'] for v in data_vendedores)
        total_pagar_usd_general = sum(v['total_con_bono'] for v in data_vendedores)
        total_pagar_bs_general = total_pagar_usd_general * tasa
        
        ws_resumen = wb.create_sheet("Resumen Semanal")
        tasa_str = f"{tasa:,.2f}" if tasa else "0.00"
        
        resumen_data = [
            ['REPORTE DE VENDEDORES', ''],
            ['', ''],
            ['Período:', f"{viernes_inicio.strftime('%d/%m/%Y')} - {jueves_fin.strftime('%d/%m/%Y')}"],
            ['Fecha de generación:', datetime.now().strftime('%d/%m/%Y %H:%M:%S')],
            ['Tasa de cambio:', f"1 USD = {tasa_str} Bs"],
            ['', ''],
            ['ESTADÍSTICAS:', ''],
            ['Total vendedores con ventas:', len(data_vendedores)],
            ['Total contratos en período:', total_contratos_general],
            ['Total a pagar (USD):', f"${total_pagar_usd_general:,.2f}"],
            ['Total a pagar (Bs):', f"Bs {total_pagar_bs_general:,.2f}"],
        ]
        
        for row_idx, row_data in enumerate(resumen_data, 1):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws_resumen.cell(row=row_idx, column=col_idx, value=value)
                if row_idx == 1:
                    cell.font = Font(bold=True, size=14, color="FF6B00")
                elif row_idx == 7:
                    cell.font = Font(bold=True)
        
        ws_resumen.column_dimensions['A'].width = 25
        ws_resumen.column_dimensions['B'].width = 30
        
        headers = ['Vendedor', 'Contratos', 'Comisión x Contrato', 'Total sin Bono', 'Bono', 'Total con Bono', 'Total en Bs', 'Rango']
        data = [[
            v['vendedor'],
            v['contratos'],
            f"${v['comision_por_contrato']}",
            f"${v['total_sin_bono']}",
            f"${v['bono']}",
            f"${v['total_con_bono']}",
            f"Bs {v['total_bs']:,.2f}",
            v['rango']
        ] for v in data_vendedores]
        
        ws_detalles = wb.create_sheet("Detalle Contratos")
        detalles_headers = ['Vendedor', 'Cliente', 'Fecha Completado', 'Plan', 'Customer ID']
        detalles_data = []
        
        for vendedor_obj in vendedores:
            contratos_vendedor = contratos.filter(creado_por=vendedor_obj).order_by('-fecha_completado')
            nombre_vendedor = vendedor_obj.get_full_name() or vendedor_obj.username
            
            for contrato in contratos_vendedor:
                detalles_data.append([
                    nombre_vendedor,
                    contrato.nombre_completo,
                    contrato.fecha_completado.strftime('%d/%m/%Y %H:%M') if contrato.fecha_completado else 'N/A',
                    contrato.plan_contratado.nombre,
                    contrato.customer_id or 'N/A'
                ])
        
        for col_idx, header in enumerate(detalles_headers, 1):
            cell = ws_detalles.cell(row=1, column=col_idx, value=header)
            cell.fill = PatternFill(start_color="FF6B00", end_color="FF6B00", fill_type="solid")
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        for row_idx, row_data in enumerate(detalles_data, 2):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws_detalles.cell(row=row_idx, column=col_idx, value=value)
                cell.alignment = Alignment(horizontal='left', vertical='center')
        
        for col_idx in range(1, len(detalles_headers) + 1):
            max_length = max(len(detalles_headers[col_idx-1]), max([len(str(row[col_idx-1])) for row in detalles_data[:100]] or [0]))
            ws_detalles.column_dimensions[get_column_letter(col_idx)].width = min(max_length + 2, 30)
    
    else:  # instaladores (NUEVO)
        ws = wb.active
        ws.title = "Reporte de Instaladores"
        
        from datetime import timedelta
        from collections import defaultdict
        
        PRECIO_INSTALACION = 15
        PRECIO_CONTRATO = 10
        PRECIOS_SOPORTES = {
            'SOPORTE': 10,
            'RETIRO': 8,
            'MUDANZA': 15,
            'RECABLEADO': 15,
        }
        
        if semana:
            try:
                fecha_referencia = datetime.strptime(semana, '%Y-%m-%d').date()
            except:
                fecha_referencia = datetime.now().date()
        else:
            fecha_referencia = datetime.now().date()
        
        dias_desde_viernes = fecha_referencia.weekday() - 4
        if dias_desde_viernes < 0:
            dias_desde_viernes += 7
        
        viernes_inicio = fecha_referencia - timedelta(days=dias_desde_viernes)
        jueves_fin = viernes_inicio + timedelta(days=6)
        
        todas_cuadrillas = Cuadrilla.objects.filter(activo=True)
        
        if cuadrilla:
            todas_cuadrillas = todas_cuadrillas.filter(id=cuadrilla)
        
        cuadrillas_dict = defaultdict(lambda: {
            'id': None,
            'cuadrilla': '',
            'instalaciones': 0,
            'monto_instalaciones': 0,
            'soportes': 0,
            'monto_soportes': 0,
            'contratos': 0,
            'monto_contratos': 0,
            'instaladores_list': []
        })
        
        for cuadrilla_obj in todas_cuadrillas:
            cuadrillas_dict[cuadrilla_obj.nombre]['id'] = cuadrilla_obj.id
            cuadrillas_dict[cuadrilla_obj.nombre]['cuadrilla'] = cuadrilla_obj.nombre
            
            perfiles = cuadrilla_obj.instaladores.all()
            nombres_instaladores = []
            for perfil in perfiles:
                if perfil.usuario:
                    nombres_instaladores.append(perfil.usuario.get_full_name() or perfil.usuario.username)
            cuadrillas_dict[cuadrilla_obj.nombre]['instaladores_list'] = nombres_instaladores
        
        # Instalaciones
        instalaciones = Instalacion.objects.filter(
            completada=True,
            fecha_creacion__date__gte=viernes_inicio,
            fecha_creacion__date__lte=jueves_fin
        ).select_related('asignacion__cuadrilla')
        
        for inst in instalaciones:
            cuadrilla_obj = inst.asignacion.cuadrilla if inst.asignacion else None
            if not cuadrilla_obj:
                continue
            nombre_cuadrilla = cuadrilla_obj.nombre
            if nombre_cuadrilla in cuadrillas_dict:
                cuadrillas_dict[nombre_cuadrilla]['instalaciones'] += 1
                cuadrillas_dict[nombre_cuadrilla]['monto_instalaciones'] += PRECIO_INSTALACION
        
        # Soportes
        soportes = Soporte.objects.filter(
            estado='COMPLETADO',
            fecha_creacion__date__gte=viernes_inicio,
            fecha_creacion__date__lte=jueves_fin
        ).select_related('cuadrilla')
        
        for sop in soportes:
            if not sop.cuadrilla:
                continue
            nombre_cuadrilla = sop.cuadrilla.nombre
            if nombre_cuadrilla in cuadrillas_dict:
                try:
                    tipo = sop.asignacion.ticket.tipo_soporte if sop.asignacion and sop.asignacion.ticket else 'SOPORTE'
                    precio = PRECIOS_SOPORTES.get(tipo, 10)
                except:
                    precio = 10
                
                cuadrillas_dict[nombre_cuadrilla]['soportes'] += 1
                cuadrillas_dict[nombre_cuadrilla]['monto_soportes'] += precio
        
        # Contratos (creados por instaladores)
        instaladores_users = User.objects.filter(groups__name='Instalador')
        
        if instalador:
            instaladores_users = instaladores_users.filter(id=instalador)
        
        for instalador_user in instaladores_users:
            perfil = PerfilUsuario.objects.filter(usuario=instalador_user).first()
            if not perfil:
                continue
            
            cuadrillas_del_instalador = perfil.cuadrillas.all()
            if not cuadrillas_del_instalador.exists():
                continue
            
            contratos_instalador = ContratoCliente.objects.filter(
                estado='COMPLETADO',
                creado_por=instalador_user,
                fecha_completado__date__gte=viernes_inicio,
                fecha_completado__date__lte=jueves_fin
            )
            
            for contrato in contratos_instalador:
                for cuadrilla_inst in cuadrillas_del_instalador:
                    nombre_cuadrilla = cuadrilla_inst.nombre
                    if nombre_cuadrilla in cuadrillas_dict:
                        cuadrillas_dict[nombre_cuadrilla]['contratos'] += 1
                        cuadrillas_dict[nombre_cuadrilla]['monto_contratos'] += PRECIO_CONTRATO
        
        tasa_obj = TasaCambio.objects.filter(activo=True).first()
        tasa = float(tasa_obj.tasa) if tasa_obj else 0
        
        data_cuadrillas = []
        for nombre, data in cuadrillas_dict.items():
            if data['instalaciones'] > 0 or data['soportes'] > 0 or data['contratos'] > 0 or cuadrilla:
                total_usd = data['monto_instalaciones'] + data['monto_soportes'] + data['monto_contratos']
                total_bs = total_usd * tasa
                data_cuadrillas.append({
                    'cuadrilla': data['cuadrilla'],
                    'instalaciones': data['instalaciones'],
                    'monto_instalaciones': data['monto_instalaciones'],
                    'soportes': data['soportes'],
                    'monto_soportes': data['monto_soportes'],
                    'contratos': data['contratos'],
                    'monto_contratos': data['monto_contratos'],
                    'total_usd': total_usd,
                    'total_bs': total_bs,
                    'instaladores_list': data['instaladores_list']
                })
        
        data_cuadrillas.sort(key=lambda x: x['instalaciones'] + x['soportes'] + x['contratos'], reverse=True)
        
        headers = ['Cuadrilla', 'Instalaciones', 'Monto Instalaciones', 'Soportes', 'Monto Soportes', 'Contratos', 'Monto Contratos', 'Total USD', 'Total Bs', 'Instaladores']
        data = [[
            item['cuadrilla'],
            item['instalaciones'],
            f"${item['monto_instalaciones']}",
            item['soportes'],
            f"${item['monto_soportes']}",
            item['contratos'],
            f"${item['monto_contratos']}",
            f"${item['total_usd']}",
            f"Bs {item['total_bs']:,.2f}",
            ', '.join(item['instaladores_list']) if item['instaladores_list'] else 'Sin instaladores'
        ] for item in data_cuadrillas]
    
    # Aplicar estilos generales
    if tipo not in ['vendedores', 'instaladores']:
        header_fill = PatternFill(start_color="FF6B00", end_color="FF6B00", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border
        
        for row_idx, row_data in enumerate(data, 2):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = border
                cell.alignment = Alignment(horizontal='left' if col_idx == 1 else 'center', vertical='center')
        
        for col in range(1, len(headers) + 1):
            max_length = max(len(str(headers[col-1])), max([len(str(row[col-1])) for row in data[:100]] or [0]))
            ws.column_dimensions[get_column_letter(col)].width = min(max_length + 2, 50)
    
    else:
        header_fill = PatternFill(start_color="FF6B00", end_color="FF6B00", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border
        
        for row_idx, row_data in enumerate(data, 2):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = border
                cell.alignment = Alignment(horizontal='left' if col_idx == 1 else 'center', vertical='center')
        
        for col in range(1, len(headers) + 1):
            max_length = max(len(str(headers[col-1])), max([len(str(row[col-1])) for row in data[:100]] or [0]))
            ws.column_dimensions[get_column_letter(col)].width = min(max_length + 2, 30)
    
    filename = f"reporte_{tipo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    
    return response


def exportar_pdf(request, tipo, reporte_tipo, fecha_desde, fecha_hasta,
                 busqueda, vendedor, plan, cuadrilla, estado,
                 tipo_soporte, estado_soporte, material, semana, instalador):
    """Exportar datos a PDF con filtros"""
    
    import io
    from reportlab.lib.pagesizes import A4, landscape
    from datetime import timedelta
    from collections import defaultdict
    
    if tipo == 'ventas':
        titulo = "Reporte de Ventas"
        
        datos = ContratoCliente.objects.filter(estado__in=['COMPLETADO', 'EN_PROCESO'])
        
        if fecha_desde:
            datos = datos.filter(fecha_creacion__date__gte=fecha_desde)
        if fecha_hasta:
            datos = datos.filter(fecha_creacion__date__lte=fecha_hasta)
        if vendedor:
            datos = datos.filter(creado_por_id=vendedor)
        if plan:
            datos = datos.filter(plan_contratado_id=plan)
        if busqueda:
            datos = datos.filter(
                Q(cliente_potencial__nombre__icontains=busqueda) |
                Q(cliente_potencial__apellido__icontains=busqueda) |
                Q(cliente_potencial__cedula__icontains=busqueda) |
                Q(customer_id__icontains=busqueda)
            )
        
        datos = datos.order_by('-fecha_creacion')
        total_registros = datos.count()
        completados = datos.filter(estado='COMPLETADO').count()
        en_proceso = datos.filter(estado='EN_PROCESO').count()
        
        if reporte_tipo == 'simple':
            headers = ['Cliente', 'Customer ID', 'ODS', 'Fecha', 'Vendedor', 'Estado']
            rows = [[
                v.nombre_completo,
                v.customer_id or 'N/A',
                v.ods or 'N/A',
                v.fecha_creacion.strftime('%d/%m/%Y'),
                v.creado_por.get_full_name() or v.creado_por.username if v.creado_por else 'N/A',
                v.get_estado_display()
            ] for v in datos]
        else:
            headers = ['ID', 'Cliente', 'Cédula', 'Teléfono', 'Plan', 'Fecha', 'Vendedor', 'Customer ID', 'ODS', 'Estado']
            rows = [[
                str(v.id),
                v.nombre_completo,
                v.cedula,
                v.telefono_principal,
                v.plan_contratado.nombre,
                v.fecha_creacion.strftime('%d/%m/%Y'),
                v.creado_por.get_full_name() or v.creado_por.username if v.creado_por else 'N/A',
                v.customer_id or 'N/A',
                v.ods or 'N/A',
                v.get_estado_display()
            ] for v in datos]
    
    elif tipo == 'instalaciones':
        titulo = "Reporte de Instalaciones"
        
        datos = Instalacion.objects.all()
        
        if fecha_desde:
            datos = datos.filter(fecha_instalacion__date__gte=fecha_desde)
        if fecha_hasta:
            datos = datos.filter(fecha_instalacion__date__lte=fecha_hasta)
        if cuadrilla:
            datos = datos.filter(asignacion__cuadrilla_id=cuadrilla)
        if estado == 'completada':
            datos = datos.filter(completada=True)
        elif estado == 'pendiente':
            datos = datos.filter(completada=False)
        if busqueda:
            datos = datos.filter(
                Q(nombre_cliente__icontains=busqueda) |
                Q(cedula_cliente__icontains=busqueda) |
                Q(customer_id__icontains=busqueda)
            )
        
        datos = datos.order_by('-fecha_instalacion')
        total_registros = datos.count()
        completadas = datos.filter(completada=True).count()
        pendientes = datos.filter(completada=False).count()
        
        if reporte_tipo == 'simple':
            headers = ['Cliente', 'Customer ID', 'ODS', 'Fecha', 'Cuadrilla', 'Estado']
            rows = []
            for i in datos:
                rows.append([
                    i.nombre_cliente,
                    i.customer_id,
                    i.orden_servicio,
                    i.fecha_instalacion.strftime('%d/%m/%Y') if i.fecha_instalacion else 'N/A',
                    i.asignacion.cuadrilla.nombre if i.asignacion and i.asignacion.cuadrilla else 'N/A',
                    'Completada' if i.completada else 'Pendiente'
                ])
        else:
            headers = ['ID', 'Cliente', 'Cédula', 'Plan', 'Cuadrilla', 'Fecha', 'Estado', 'Modelo', 'Serial', 'Metros']
            rows = []
            for i in datos:
                rows.append([
                    str(i.id),
                    i.nombre_cliente,
                    i.cedula_cliente,
                    i.plan,
                    i.asignacion.cuadrilla.nombre if i.asignacion and i.asignacion.cuadrilla else 'N/A',
                    i.fecha_instalacion.strftime('%d/%m/%Y') if i.fecha_instalacion else 'N/A',
                    'Completada' if i.completada else 'Pendiente',
                    i.modelo_modem.nombre if i.modelo_modem else 'N/A',
                    i.sn_modem or 'N/A',
                    str(i.metros_utilizados)
                ])
    
    elif tipo == 'soportes':
        titulo = "Reporte de Soportes"
        
        datos = Soporte.objects.all()
        
        if fecha_desde:
            datos = datos.filter(fecha_hora_servicio__date__gte=fecha_desde)
        if fecha_hasta:
            datos = datos.filter(fecha_hora_servicio__date__lte=fecha_hasta)
        if tipo_soporte:
            datos = datos.filter(asignacion__ticket__tipo_soporte=tipo_soporte)
        if estado_soporte:
            datos = datos.filter(estado=estado_soporte)
        if busqueda:
            datos = datos.filter(
                Q(asignacion__ticket__nombre__icontains=busqueda) |
                Q(asignacion__ticket__apellido__icontains=busqueda) |
                Q(asignacion__ticket__cedula__icontains=busqueda)
            )
        
        datos = datos.order_by('-fecha_hora_servicio', '-fecha_creacion')
        total_registros = datos.count()
        completados = datos.filter(estado='COMPLETADO').count()
        pendientes = datos.filter(estado='PENDIENTE').count()
        en_proceso = datos.filter(estado='EN_PROCESO').count()
        
        if reporte_tipo == 'simple':
            headers = ['Cliente', 'Customer ID', 'Ticket Padre', 'Fecha', 'Cuadrilla', 'Estado']
            rows = []
            for s in datos:
                try:
                    cliente = s.asignacion.ticket.nombre_completo if s.asignacion and s.asignacion.ticket else 'N/A'
                    customer_id = s.asignacion.ticket.customer_id if s.asignacion and s.asignacion.ticket else 'N/A'
                    ticket_padre = s.asignacion.ticket.ticket_padre if s.asignacion and s.asignacion.ticket else 'N/A'
                except:
                    cliente = 'N/A'
                    customer_id = 'N/A'
                    ticket_padre = 'N/A'
                
                rows.append([
                    cliente,
                    customer_id,
                    ticket_padre,
                    s.fecha_hora_servicio.strftime('%d/%m/%Y') if s.fecha_hora_servicio else s.fecha_creacion.strftime('%d/%m/%Y'),
                    s.cuadrilla.nombre if s.cuadrilla else 'N/A',
                    s.get_estado_display() if hasattr(s, 'get_estado_display') else s.estado
                ])
        else:
            headers = ['ID', 'Ticket Padre', 'Cliente', 'Cédula', 'Tipo', 'Estado', 'Fecha', 'Falla', 'Solución']
            rows = []
            for s in datos:
                try:
                    ticket_padre = s.asignacion.ticket.ticket_padre if s.asignacion and s.asignacion.ticket else 'N/A'
                    cliente = s.asignacion.ticket.nombre_completo if s.asignacion and s.asignacion.ticket else 'N/A'
                    cedula = s.asignacion.ticket.cedula if s.asignacion and s.asignacion.ticket else 'N/A'
                    tipo_display = s.asignacion.ticket.get_tipo_soporte_display() if s.asignacion and s.asignacion.ticket else 'N/A'
                except:
                    ticket_padre = 'N/A'
                    cliente = 'N/A'
                    cedula = 'N/A'
                    tipo_display = 'N/A'
                
                rows.append([
                    str(s.id),
                    ticket_padre,
                    cliente,
                    cedula,
                    tipo_display,
                    s.get_estado_display() if hasattr(s, 'get_estado_display') else s.estado,
                    s.fecha_hora_servicio.strftime('%d/%m/%Y') if s.fecha_hora_servicio else s.fecha_creacion.strftime('%d/%m/%Y'),
                    (s.falla_encontrada[:80] + '...') if s.falla_encontrada and len(s.falla_encontrada) > 80 else (s.falla_encontrada or 'N/A'),
                    (s.solucion[:80] + '...') if s.solucion and len(s.solucion) > 80 else (s.solucion or 'N/A')
                ])
    
    elif tipo == 'inventario':
        titulo = "Reporte de Inventario"
        
        datos = InventarioGlobal.objects.select_related('material')
        
        if material:
            datos = datos.filter(material_id=material)
        if busqueda:
            datos = datos.filter(material__nombre__icontains=busqueda)
        
        datos = datos.order_by('material__nombre')
        total_registros = datos.count()
        total_unidades = sum(item.cantidad for item in datos)
        bajo_stock = sum(1 for item in datos if item.esta_bajo_stock)
        
        if reporte_tipo == 'simple':
            headers = ['Material', 'Cantidad', 'Mínimo', 'Estado']
            rows = [[
                item.material.nombre,
                str(item.cantidad),
                str(item.cantidad_minima),
                'Bajo stock' if item.esta_bajo_stock else 'Normal'
            ] for item in datos]
        else:
            headers = ['ID', 'Material', 'Cantidad', 'Mínimo', 'Estado', 'Última Actualización', 'Actualizado Por']
            rows = [[
                str(item.id),
                item.material.nombre,
                str(item.cantidad),
                str(item.cantidad_minima),
                'Bajo stock' if item.esta_bajo_stock else 'Normal',
                item.ultima_actualizacion.strftime('%d/%m/%Y %H:%M'),
                item.actualizado_por.get_full_name() or item.actualizado_por.username if item.actualizado_por else 'Sistema'
            ] for item in datos]
    
    elif tipo == 'vendedores':
        titulo = "Reporte de Vendedores"
        
        if semana:
            try:
                fecha_referencia = datetime.strptime(semana, '%Y-%m-%d').date()
            except:
                fecha_referencia = datetime.now().date()
        else:
            fecha_referencia = datetime.now().date()
        
        dias_desde_viernes = fecha_referencia.weekday() - 4
        if dias_desde_viernes < 0:
            dias_desde_viernes += 7
        
        viernes_inicio = fecha_referencia - timedelta(days=dias_desde_viernes)
        jueves_fin = viernes_inicio + timedelta(days=6)
        
        contratos = ContratoCliente.objects.filter(
            estado='COMPLETADO',
            fecha_completado__date__gte=viernes_inicio,
            fecha_completado__date__lte=jueves_fin
        )
        
        if vendedor:
            contratos = contratos.filter(creado_por_id=vendedor)
        
        vendedores = User.objects.filter(
            groups__name__in=['Vendedor', 'Supervisor']
        ).distinct()
        
        if vendedor:
            vendedores = vendedores.filter(id=vendedor)
        
        if busqueda:
            vendedores = vendedores.filter(
                Q(first_name__icontains=busqueda) |
                Q(username__icontains=busqueda) |
                Q(last_name__icontains=busqueda)
            )
        
        tasa_obj = TasaCambio.objects.filter(activo=True).first()
        tasa = float(tasa_obj.tasa) if tasa_obj else 0
        
        data_vendedores = []
        
        for vendedor_obj in vendedores:
            contratos_vendedor = contratos.filter(creado_por=vendedor_obj)
            total_contratos = contratos_vendedor.count()
            
            if total_contratos > 0 or not vendedor:
                if total_contratos >= 1 and total_contratos <= 5:
                    comision_por_contrato = 8
                    bono = 20
                    total_precio = total_contratos * 8
                    rango = "1-5 contratos"
                elif total_contratos >= 6 and total_contratos <= 10:
                    comision_por_contrato = 10
                    bono = 40
                    total_precio = total_contratos * 10
                    rango = "6-10 contratos"
                elif total_contratos >= 11:
                    comision_por_contrato = 10
                    bono = 60
                    total_precio = total_contratos * 10
                    rango = "11+ contratos"
                else:
                    comision_por_contrato = 0
                    bono = 0
                    total_precio = 0
                    rango = "Sin contratos"
                
                total_con_bono = total_precio + bono
                total_bs = total_con_bono * tasa
                
                data_vendedores.append({
                    'vendedor': vendedor_obj.get_full_name() or vendedor_obj.username,
                    'contratos': total_contratos,
                    'comision_por_contrato': comision_por_contrato,
                    'total_sin_bono': total_precio,
                    'bono': bono,
                    'total_con_bono': total_con_bono,
                    'total_bs': total_bs,
                    'rango': rango
                })
        
        data_vendedores.sort(key=lambda x: x['contratos'], reverse=True)
        
        total_contratos_general = sum(v['contratos'] for v in data_vendedores)
        total_pagar_usd_general = sum(v['total_con_bono'] for v in data_vendedores)
        total_pagar_bs_general = total_pagar_usd_general * tasa
        
        rows = [[
            v['vendedor'],
            str(v['contratos']),
            f"${v['comision_por_contrato']}",
            f"${v['total_sin_bono']}",
            f"${v['bono']}",
            f"${v['total_con_bono']}",
            f"Bs {v['total_bs']:,.2f}",
            v['rango']
        ] for v in data_vendedores]
        
        headers = ['Vendedor', 'Contratos', 'Comisión x Contrato', 'Total sin Bono', 'Bono', 'Total con Bono', 'Total en Bs', 'Rango']
        
        total_registros = len(rows)
        completados = total_contratos_general
        en_proceso = 0
    
    else:  # instaladores
        titulo = "Reporte de Instaladores"
        
        PRECIO_INSTALACION = 15
        PRECIO_CONTRATO = 10
        PRECIOS_SOPORTES = {
            'SOPORTE': 10,
            'RETIRO': 8,
            'MUDANZA': 15,
            'RECABLEADO': 15,
        }
        
        if semana:
            try:
                fecha_referencia = datetime.strptime(semana, '%Y-%m-%d').date()
            except:
                fecha_referencia = datetime.now().date()
        else:
            fecha_referencia = datetime.now().date()
        
        dias_desde_viernes = fecha_referencia.weekday() - 4
        if dias_desde_viernes < 0:
            dias_desde_viernes += 7
        
        viernes_inicio = fecha_referencia - timedelta(days=dias_desde_viernes)
        jueves_fin = viernes_inicio + timedelta(days=6)
        
        todas_cuadrillas = Cuadrilla.objects.filter(activo=True)
        
        if cuadrilla:
            todas_cuadrillas = todas_cuadrillas.filter(id=cuadrilla)
        
        cuadrillas_dict = defaultdict(lambda: {
            'cuadrilla': '',
            'instalaciones': 0,
            'monto_instalaciones': 0,
            'soportes': 0,
            'monto_soportes': 0,
            'contratos': 0,
            'monto_contratos': 0,
            'instaladores_list': []
        })
        
        for cuadrilla_obj in todas_cuadrillas:
            cuadrillas_dict[cuadrilla_obj.nombre]['cuadrilla'] = cuadrilla_obj.nombre
            perfiles = cuadrilla_obj.instaladores.all()
            nombres_instaladores = []
            for perfil in perfiles:
                if perfil.usuario:
                    nombres_instaladores.append(perfil.usuario.get_full_name() or perfil.usuario.username)
            cuadrillas_dict[cuadrilla_obj.nombre]['instaladores_list'] = nombres_instaladores
        
        instalaciones = Instalacion.objects.filter(
            completada=True,
            fecha_creacion__date__gte=viernes_inicio,
            fecha_creacion__date__lte=jueves_fin
        ).select_related('asignacion__cuadrilla')
        
        for inst in instalaciones:
            cuadrilla_obj = inst.asignacion.cuadrilla if inst.asignacion else None
            if cuadrilla_obj and cuadrilla_obj.nombre in cuadrillas_dict:
                cuadrillas_dict[cuadrilla_obj.nombre]['instalaciones'] += 1
                cuadrillas_dict[cuadrilla_obj.nombre]['monto_instalaciones'] += PRECIO_INSTALACION
        
        soportes = Soporte.objects.filter(
            estado='COMPLETADO',
            fecha_creacion__date__gte=viernes_inicio,
            fecha_creacion__date__lte=jueves_fin
        ).select_related('cuadrilla')
        
        for sop in soportes:
            if sop.cuadrilla and sop.cuadrilla.nombre in cuadrillas_dict:
                try:
                    tipo = sop.asignacion.ticket.tipo_soporte if sop.asignacion and sop.asignacion.ticket else 'SOPORTE'
                    precio = PRECIOS_SOPORTES.get(tipo, 10)
                except:
                    precio = 10
                cuadrillas_dict[sop.cuadrilla.nombre]['soportes'] += 1
                cuadrillas_dict[sop.cuadrilla.nombre]['monto_soportes'] += precio
        
        instaladores_users = User.objects.filter(groups__name='Instalador')
        
        if instalador:
            instaladores_users = instaladores_users.filter(id=instalador)
        
        for instalador_user in instaladores_users:
            perfil = PerfilUsuario.objects.filter(usuario=instalador_user).first()
            if not perfil:
                continue
            cuadrillas_del_instalador = perfil.cuadrillas.all()
            if not cuadrillas_del_instalador.exists():
                continue
            contratos_instalador = ContratoCliente.objects.filter(
                estado='COMPLETADO',
                creado_por=instalador_user,
                fecha_completado__date__gte=viernes_inicio,
                fecha_completado__date__lte=jueves_fin
            )
            for contrato in contratos_instalador:
                for cuadrilla_inst in cuadrillas_del_instalador:
                    if cuadrilla_inst.nombre in cuadrillas_dict:
                        cuadrillas_dict[cuadrilla_inst.nombre]['contratos'] += 1
                        cuadrillas_dict[cuadrilla_inst.nombre]['monto_contratos'] += PRECIO_CONTRATO
        
        tasa_obj = TasaCambio.objects.filter(activo=True).first()
        tasa = float(tasa_obj.tasa) if tasa_obj else 0
        
        data_cuadrillas = []
        for nombre, data in cuadrillas_dict.items():
            if data['instalaciones'] > 0 or data['soportes'] > 0 or data['contratos'] > 0 or cuadrilla:
                total_usd = data['monto_instalaciones'] + data['monto_soportes'] + data['monto_contratos']
                total_bs = total_usd * tasa
                data_cuadrillas.append({
                    'cuadrilla': data['cuadrilla'],
                    'instalaciones': data['instalaciones'],
                    'monto_instalaciones': data['monto_instalaciones'],
                    'soportes': data['soportes'],
                    'monto_soportes': data['monto_soportes'],
                    'contratos': data['contratos'],
                    'monto_contratos': data['monto_contratos'],
                    'total_usd': total_usd,
                    'total_bs': total_bs,
                    'instaladores_list': data['instaladores_list']
                })
        
        data_cuadrillas.sort(key=lambda x: x['instalaciones'] + x['soportes'] + x['contratos'], reverse=True)
        
        rows = [[
            item['cuadrilla'],
            item['instalaciones'],
            f"${item['monto_instalaciones']}",
            item['soportes'],
            f"${item['monto_soportes']}",
            item['contratos'],
            f"${item['monto_contratos']}",
            f"${item['total_usd']}",
            f"Bs {item['total_bs']:,.2f}",
            ', '.join(item['instaladores_list']) if item['instaladores_list'] else 'Sin instaladores'
        ] for item in data_cuadrillas]
        
        headers = ['Cuadrilla', 'Instalaciones', 'Monto Instalaciones', 'Soportes', 'Monto Soportes', 'Contratos', 'Monto Contratos', 'Total USD', 'Total Bs', 'Instaladores']
        
        total_registros = len(rows)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=TA_CENTER, textColor=colors.HexColor('#FF6B00'))
    title = Paragraph(titulo, title_style)
    
    date_style = ParagraphStyle('DateStyle', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER)
    fecha_texto = f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    
    if tipo == 'vendedores':
        fecha_texto += f" | Período: {viernes_inicio.strftime('%d/%m/%Y')} - {jueves_fin.strftime('%d/%m/%Y')}"
        fecha_texto += f" | Tasa: 1 USD = {tasa:,.2f} Bs"
    elif tipo == 'instaladores':
        fecha_texto += f" | Período: {viernes_inicio.strftime('%d/%m/%Y')} - {jueves_fin.strftime('%d/%m/%Y')}"
        fecha_texto += f" | Tasa: 1 USD = {tasa:,.2f} Bs"
    elif fecha_desde or fecha_hasta:
        fecha_texto += f" | Periodo: {fecha_desde or 'inicio'} al {fecha_hasta or 'actual'}"
    
    fecha_paragraph = Paragraph(fecha_texto, date_style)
    
    stats_data = [['ESTADÍSTICAS', '']]
    
    if tipo == 'ventas':
        stats_data.extend([
            ['Total contratos:', str(len(rows))],
            ['Completados:', str(completados)],
            ['En proceso:', str(en_proceso)],
        ])
    elif tipo == 'instalaciones':
        stats_data.extend([
            ['Total instalaciones:', str(len(rows))],
            ['Completadas:', str(completadas)],
            ['Pendientes:', str(pendientes)],
        ])
    elif tipo == 'soportes':
        stats_data.extend([
            ['Total soportes:', str(len(rows))],
            ['Completados:', str(completados)],
            ['En proceso:', str(en_proceso)],
            ['Pendientes:', str(pendientes)],
        ])
    elif tipo == 'inventario':
        stats_data.extend([
            ['Total materiales:', str(total_registros)],
            ['Total unidades:', str(total_unidades)],
            ['Bajo stock:', str(bajo_stock)],
        ])
    elif tipo == 'vendedores':
        stats_data.extend([
            ['Período:', f"{viernes_inicio.strftime('%d/%m/%Y')} - {jueves_fin.strftime('%d/%m/%Y')}"],
            ['Total vendedores con ventas:', str(len(rows))],
            ['Total contratos en período:', str(total_contratos_general)],
            ['Total a pagar (USD):', f"${total_pagar_usd_general:,.2f}"],
            ['Total a pagar (Bs):', f"Bs {total_pagar_bs_general:,.2f}"],
            ['Tasa de cambio:', f"1 USD = {tasa:,.2f} Bs"],
        ])
    else:  # instaladores
        total_instalaciones = sum(r[1] for r in rows if isinstance(r[1], (int, float)))
        total_soportes = sum(r[3] for r in rows if isinstance(r[3], (int, float)))
        total_contratos = sum(r[5] for r in rows if isinstance(r[5], (int, float)))
        total_pagar_usd = sum(float(r[7].replace('$', '').replace(',', '')) for r in rows)
        total_pagar_bs = sum(float(r[8].replace('Bs ', '').replace('Bs', '').replace(',', '').strip()) for r in rows)
        
        stats_data.extend([
            ['Período:', f"{viernes_inicio.strftime('%d/%m/%Y')} - {jueves_fin.strftime('%d/%m/%Y')}"],
            ['Total cuadrillas:', str(len(rows))],
            ['Instalaciones:', str(total_instalaciones)],
            ['Soportes:', str(total_soportes)],
            ['Contratos:', str(total_contratos)],
            ['Total a pagar (USD):', f"${total_pagar_usd:,.2f}"],
            ['Total a pagar (Bs):', f"Bs {total_pagar_bs:,.2f}"],
            ['Tasa de cambio:', f"1 USD = {tasa:,.2f} Bs"],
            ['Precio instalación:', f"${PRECIO_INSTALACION}"],
            ['Precio contrato:', f"${PRECIO_CONTRATO}"],
            ['Precios soportes:', 'Soporte: $10, Retiro: $8, Mudanza: $15, Recableado: $15'],
        ])
    
    stats_table = Table(stats_data, colWidths=[150, 200])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF6B00')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements = [title, Spacer(1, 12), fecha_paragraph, Spacer(1, 12), stats_table, Spacer(1, 20)]
    
    if rows:
        max_rows_per_page = 15
        num_pages = (len(rows) + max_rows_per_page - 1) // max_rows_per_page
        
        for page in range(num_pages):
            start_idx = page * max_rows_per_page
            end_idx = min(start_idx + max_rows_per_page, len(rows))
            page_rows = rows[start_idx:end_idx]
            
            table_data = [headers] + page_rows
            table = Table(table_data, repeatRows=1)
            
            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF6B00')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            
            table.setStyle(TableStyle(table_style))
            elements.append(table)
            
            if page < num_pages - 1:
                elements.append(PageBreak())
    else:
        no_data = Paragraph("No hay datos disponibles para los filtros seleccionados", styles['Normal'])
        elements.append(no_data)
    
    doc.build(elements)
    
    buffer.seek(0)
    filename = f"reporte_{tipo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response