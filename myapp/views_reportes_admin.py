from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Sum
from datetime import datetime
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
from .models import ContratoCliente, Instalacion, Soporte, User, Plan, Cuadrilla, VentaDirecta, Material, MovimientoInventario, InventarioGlobal


def es_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name='Administrador').exists())


@login_required
@user_passes_test(es_admin)
def reportes_view(request):
    """Vista principal de reportes unificada"""
    from myapp.models import User, Plan, Cuadrilla, Material
    
    vendedores = User.objects.filter(
            groups__name__in=['Vendedor', 'Supervisor', 'Instalador']
        ).distinct().order_by('first_name', 'username',activo=True)
    planes = Plan.objects.filter(activo=True)
    cuadrillas = Cuadrilla.objects.filter(activo=True)
    materiales = Material.objects.filter(activo=True)
    
    context = {
        'vendedores': vendedores,
        'planes': planes,
        'cuadrillas': cuadrillas,
        'materiales': materiales,
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
    
    if formato == 'excel':
        return exportar_excel(request, tipo, reporte_tipo, fecha_desde, fecha_hasta, 
                              busqueda, vendedor, plan, cuadrilla, estado, 
                              tipo_soporte, estado_soporte, material)
    else:
        return exportar_pdf(request, tipo, reporte_tipo, fecha_desde, fecha_hasta,
                            busqueda, vendedor, plan, cuadrilla, estado,
                            tipo_soporte, estado_soporte, material)


def exportar_excel(request, tipo, reporte_tipo, fecha_desde, fecha_hasta,
                   busqueda, vendedor, plan, cuadrilla, estado,
                   tipo_soporte, estado_soporte, material):
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
    
    else:  # inventario
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
    
    # Estilos para todas las hojas
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
            cell.alignment = Alignment(horizontal='left', vertical='center')
            
            # Colorear según estado (columna Estado)
            if headers[col_idx-1] == 'Estado':
                if value == 'Completado' or value == 'Completada' or value == 'Normal':
                    cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                    if value == 'Normal':
                        cell.font = Font(color="006100")
                elif value == 'En Proceso' or value == 'Pendiente' or value == 'Bajo stock':
                    if value == 'Bajo stock':
                        cell.fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                        cell.font = Font(color="9C0006")
                    else:
                        cell.fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
                        cell.font = Font(color="9C6500")
    
    for col in range(1, len(headers) + 1):
        max_length = max(len(str(headers[col-1])), max([len(str(row[col-1])) for row in data[:100]] or [0]))
        ws.column_dimensions[get_column_letter(col)].width = min(max_length + 2, 50)
    
    filename = f"reporte_{tipo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    
    return response


def exportar_pdf(request, tipo, reporte_tipo, fecha_desde, fecha_hasta,
                 busqueda, vendedor, plan, cuadrilla, estado,
                 tipo_soporte, estado_soporte, material):
    """Exportar datos a PDF con filtros"""
    
    import io
    from reportlab.lib.pagesizes import A4, landscape
    
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
    
    else:  # inventario
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
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=TA_CENTER, textColor=colors.HexColor('#FF6B00'))
    title = Paragraph(titulo, title_style)
    
    date_style = ParagraphStyle('DateStyle', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER)
    fecha_texto = f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    if fecha_desde or fecha_hasta:
        fecha_texto += f" | Periodo: {fecha_desde or 'inicio'} al {fecha_hasta or 'actual'}"
    fecha_paragraph = Paragraph(fecha_texto, date_style)
    
    # Estadísticas
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
    else:
        stats_data.extend([
            ['Total materiales:', str(total_registros)],
            ['Total unidades:', str(total_unidades)],
            ['Bajo stock:', str(bajo_stock)],
        ])
    
    stats_table = Table(stats_data, colWidths=[150, 100])
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
        # Dividir en múltiples páginas si es necesario
        max_rows_per_page = 20
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
            
            # Colorear según estado (última columna)
            if tipo != 'inventario':
                for i, row in enumerate(page_rows, 1):
                    estado = row[-1]  # Última columna es Estado
                    col_idx = len(headers) - 1
                    if estado == 'Completado' or estado == 'Completada':
                        table_style.append(('BACKGROUND', (col_idx, i), (col_idx, i), colors.HexColor('#C6EFCE')))
                        table_style.append(('TEXTCOLOR', (col_idx, i), (col_idx, i), colors.HexColor('#006100')))
                    elif estado == 'En Proceso' or estado == 'Pendiente':
                        table_style.append(('BACKGROUND', (col_idx, i), (col_idx, i), colors.HexColor('#FFEB9C')))
                        table_style.append(('TEXTCOLOR', (col_idx, i), (col_idx, i), colors.HexColor('#9C6500')))
                    elif estado == 'Bajo stock':
                        table_style.append(('BACKGROUND', (col_idx, i), (col_idx, i), colors.HexColor('#FFC7CE')))
                        table_style.append(('TEXTCOLOR', (col_idx, i), (col_idx, i), colors.HexColor('#9C0006')))
            
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