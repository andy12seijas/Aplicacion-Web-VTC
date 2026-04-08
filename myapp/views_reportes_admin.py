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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import ContratoCliente, Instalacion, Soporte, User, Plan, Cuadrilla, VentaDirecta


def es_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name='Administrador').exists())


@login_required
@user_passes_test(es_admin)
def reportes_view(request):
    """Vista principal de reportes"""
    from myapp.models import User, Plan, Cuadrilla
    
    vendedores = User.objects.filter(groups__name='Vendedor').distinct()
    planes = Plan.objects.filter(activo=True)
    cuadrillas = Cuadrilla.objects.filter(activo=True)
    
    context = {
        'vendedores': vendedores,
        'planes': planes,
        'cuadrillas': cuadrillas,
    }
    return render(request, 'Admin/reporte.html', context)


@login_required
@user_passes_test(es_admin)
def reporte_ventas_json(request):
    """API para obtener datos de ventas con paginación backend"""
    
    tipo_reporte = request.GET.get('tipo', 'simple')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    vendedor_id = request.GET.get('vendedor', '')
    plan_id = request.GET.get('plan', '')
    busqueda = request.GET.get('busqueda', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 15))
    
    # Base de consulta - Contratos COMPLETADOS
    ventas = ContratoCliente.objects.filter(estado='COMPLETADO')
    
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
    
    # Contar total antes de paginar
    total_registros = ventas.count()
    
    # Aplicar paginación
    paginator = Paginator(ventas, per_page)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    # Convertir datos a JSON
    if tipo_reporte == 'simple':
        data_list = []
        for venta in page_obj:
            data_list.append({
                'id': venta.id,
                'cliente': venta.nombre_completo,
                'cedula': venta.cedula,
                'plan': venta.plan_contratado.nombre,
                'fecha': venta.fecha_creacion.strftime('%d/%m/%Y'),
                'vendedor': venta.creado_por.get_full_name() or venta.creado_por.username if venta.creado_por else 'N/A',
                'customer_id': venta.customer_id or 'N/A',
                'ods': venta.ods or 'N/A',
                'estado': venta.get_estado_display(),
            })
    else:
        data_list = []
        for venta in page_obj:
            data_list.append({
                'id': venta.id,
                'cliente': venta.nombre_completo,
                'cedula': venta.cedula,
                'telefono': venta.telefono_principal,
                'otro_telefono': venta.otro_telefono or 'N/A',
                'correo': venta.correo_electronico,
                'direccion': venta.direccion_detallada[:100] if venta.direccion_detallada else 'N/A',
                'plan': venta.plan_contratado.nombre,
                'simple_plus': venta.simple_plus,
                'modalidad': venta.modalidad_equipo.nombre,
                'tipo_vivienda': venta.tipo_vivienda.nombre,
                'red': venta.red.nombre,
                'fecha_nacimiento': venta.fecha_nacimiento.strftime('%d/%m/%Y'),
                'fecha_creacion': venta.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                'vendedor': venta.creado_por.get_full_name() or venta.creado_por.username if venta.creado_por else 'N/A',
                'customer_id': venta.customer_id or 'N/A',
                'ods': venta.ods or 'N/A',
                'atr': venta.atr or 'N/A',
                'estado': venta.get_estado_display(),
            })
    
    # Estadísticas (totales sin paginación)
    vendedores_stats = list(ventas.values('creado_por__username').annotate(count=Count('id')).order_by('-count')[:10])
    planes_stats = list(ventas.values('plan_contratado__nombre').annotate(count=Count('id')).order_by('-count')[:10])
    
    estadisticas = {
        'total_ventas': total_registros,
        'vendedores': vendedores_stats,
        'planes': planes_stats,
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
    """API para obtener datos de instalaciones con paginación backend"""
    
    tipo_reporte = request.GET.get('tipo', 'simple')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    cuadrilla_id = request.GET.get('cuadrilla', '')
    estado = request.GET.get('estado', '')
    busqueda = request.GET.get('busqueda', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 6))
    
    instalaciones = Instalacion.objects.all()
    
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
    if busqueda:
        instalaciones = instalaciones.filter(
            Q(nombre_cliente__icontains=busqueda) |
            Q(cedula_cliente__icontains=busqueda)
        )
    
    total_registros = instalaciones.count()
    
    # Paginación
    paginator = Paginator(instalaciones, 5)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    if tipo_reporte == 'simple':
        data_list = []
        for inst in page_obj:
            if inst.asignacion.contrato:
                origen = "Contrato"
                customer_id = inst.asignacion.contrato.customer_id or 'N/A'
                ods = inst.asignacion.contrato.ods or 'N/A'
            else:
                origen = "Venta Directa"
                customer_id = inst.asignacion.venta_directa.customer_id or 'N/A'
                ods = inst.asignacion.venta_directa.nro_orden or 'N/A'
            
            data_list.append({
                'id': inst.id,
                'cliente': inst.nombre_cliente,
                'cedula': inst.cedula_cliente,
                'plan': inst.plan,
                'origen': origen,
                'customer_id': customer_id,
                'ods': ods,
                'cuadrilla': inst.asignacion.cuadrilla.nombre if inst.asignacion.cuadrilla else 'N/A',
                'fecha': inst.fecha_instalacion.strftime('%d/%m/%Y') if inst.fecha_instalacion else 'No registrada',
                'estado': 'Completada' if inst.completada else 'Pendiente',
                'metros': inst.metros_utilizados,
            })
    else:
        data_list = []
        for inst in page_obj:
            if inst.asignacion.contrato:
                origen = "Contrato"
                contrato = inst.asignacion.contrato
                customer_id = contrato.customer_id or 'N/A'
                ods = contrato.ods or 'N/A'
                atr = contrato.atr or '*VTC Conexiones'
                vendedor = contrato.creado_por.get_full_name() or contrato.creado_por.username if contrato.creado_por else 'N/A'
                orden_servicio = contrato.ods or 'N/A'
                direccion = contrato.direccion_detallada[:100] if contrato.direccion_detallada else "N/A"
            else:
                origen = "Venta Directa"
                venta = inst.asignacion.venta_directa
                customer_id = venta.customer_id or 'N/A'
                ods = venta.nro_orden or 'N/A'
                atr = '*VTC Conexiones'
                vendedor = venta.creado_por.get_full_name() or venta.creado_por.username if venta.creado_por else 'N/A'
                orden_servicio = venta.nro_orden or 'N/A'
                direccion = "N/A"
            
            data_list.append({
                'id': inst.id,
                'cliente': inst.nombre_cliente,
                'cedula': inst.cedula_cliente,
                'direccion': direccion,
                'plan': inst.plan,
                'origen': origen,
                'customer_id': customer_id,
                'ods': ods,
                'atr': atr,
                'vendedor': vendedor,
                'orden_servicio': orden_servicio,
                'cuadrilla': inst.asignacion.cuadrilla.nombre if inst.asignacion.cuadrilla else 'N/A',
                'fecha_instalacion': inst.fecha_instalacion.strftime('%d/%m/%Y %H:%M') if inst.fecha_instalacion else 'No registrada',
                'fecha_creacion': inst.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                'estado': 'Completada' if inst.completada else 'Pendiente',
                'modelo_modem': inst.modelo_modem.nombre if inst.modelo_modem else 'N/A',
                'sn_modem': inst.sn_modem or 'N/A',
                'mac_modem': inst.mac_modem or 'N/A',
                'metros_utilizados': inst.metros_utilizados,
                'conectores': inst.conectores or 0,
                'rosetas': inst.rosetas or 0,
                'patch_cord': inst.patch_cord or 0,
                'tensores': inst.tensores or 0,
                'feeder': inst.feeder or 'N/A',
                'caja': inst.caja or 'N/A',
                'puerto': inst.puerto_utilizado or 'N/A',
            })
    
    estadisticas = {
        'total_instalaciones': total_registros,
        'completadas': instalaciones.filter(completada=True).count(),
        'pendientes': instalaciones.filter(completada=False).count(),
        'metros_totales': sum(inst.metros_utilizados for inst in instalaciones[:1000]),
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
    """API para obtener datos de soportes con paginación backend"""
    
    tipo_reporte = request.GET.get('tipo', 'simple')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    tipo_soporte = request.GET.get('tipo_soporte', '')
    estado = request.GET.get('estado', '')
    busqueda = request.GET.get('busqueda', '')
    page = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 15))
    
    soportes = Soporte.objects.all()
    
    if fecha_desde:
        soportes = soportes.filter(fecha_hora_servicio__date__gte=fecha_desde)
    if fecha_hasta:
        soportes = soportes.filter(fecha_hora_servicio__date__lte=fecha_hasta)
    if tipo_soporte:
        soportes = soportes.filter(tipo=tipo_soporte)
    if estado:
        soportes = soportes.filter(estado=estado)
    if busqueda:
        soportes = soportes.filter(
            Q(instalacion__nombre_cliente__icontains=busqueda) |
            Q(instalacion__cedula_cliente__icontains=busqueda) |
            Q(falla_encontrada__icontains=busqueda)
        )
    
    total_registros = soportes.count()
    
    # Paginación
    paginator = Paginator(soportes, per_page)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    if tipo_reporte == 'simple':
        data_list = []
        for sop in page_obj:
            data_list.append({
                'id': sop.id,
                'cliente': sop.nombre_cliente,
                'cedula': sop.cedula_cliente,
                'tipo': sop.get_tipo_display(),
                'estado': sop.get_estado_display(),
                'fecha': sop.fecha_hora_servicio.strftime('%d/%m/%Y'),
                'falla': sop.falla_encontrada[:50] + '...' if len(sop.falla_encontrada) > 50 else sop.falla_encontrada,
            })
    else:
        data_list = []
        for sop in page_obj:
            data_list.append({
                'id': sop.id,
                'cliente': sop.nombre_cliente,
                'cedula': sop.cedula_cliente,
                'tipo': sop.get_tipo_display(),
                'estado': sop.get_estado_display(),
                'fecha_servicio': sop.fecha_hora_servicio.strftime('%d/%m/%Y %H:%M'),
                'falla_encontrada': sop.falla_encontrada[:100] if sop.falla_encontrada else 'N/A',
                'solucion': sop.solucion[:100] if sop.solucion else 'N/A',
            })
    
    estadisticas = {
        'total_soportes': total_registros,
        'pendientes': soportes.filter(estado__in=['PENDIENTE', 'EN_PROCESO']).count(),
        'completados': soportes.filter(estado='COMPLETADO').count(),
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
def exportar_excel(request):
    """Exportar datos a Excel"""
    
    tipo = request.GET.get('tipo', 'ventas')
    reporte_tipo = request.GET.get('reporte_tipo', 'simple')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    wb = Workbook()
    
    if tipo == 'ventas':
        ws = wb.active
        ws.title = "Reporte de Ventas"
        
        ventas = ContratoCliente.objects.filter(estado='COMPLETADO')
        if fecha_desde:
            ventas = ventas.filter(fecha_creacion__date__gte=fecha_desde)
        if fecha_hasta:
            ventas = ventas.filter(fecha_creacion__date__lte=fecha_hasta)
        
        if reporte_tipo == 'simple':
            headers = ['ID', 'Cliente', 'Cédula', 'Plan', 'Fecha', 'Vendedor', 'Customer ID', 'ODS', 'Estado']
            data = [[
                v.id, v.nombre_completo, v.cedula, v.plan_contratado.nombre,
                v.fecha_creacion.strftime('%d/%m/%Y'),
                v.creado_por.get_full_name() or v.creado_por.username if v.creado_por else 'N/A',
                v.customer_id or 'N/A', v.ods or 'N/A', v.get_estado_display()
            ] for v in ventas]
        else:
            headers = ['ID', 'Cliente', 'Cédula', 'Teléfono', 'Correo', 'Plan', 'Fecha', 'Vendedor', 'Customer ID', 'ODS', 'Estado']
            data = [[
                v.id, v.nombre_completo, v.cedula, v.telefono_principal, v.correo_electronico,
                v.plan_contratado.nombre, v.fecha_creacion.strftime('%d/%m/%Y'),
                v.creado_por.get_full_name() or v.creado_por.username if v.creado_por else 'N/A',
                v.customer_id or 'N/A', v.ods or 'N/A', v.get_estado_display()
            ] for v in ventas]
    
    elif tipo == 'instalaciones':
        ws = wb.active
        ws.title = "Reporte de Instalaciones"
        
        instalaciones = Instalacion.objects.all()
        if fecha_desde:
            instalaciones = instalaciones.filter(fecha_instalacion__date__gte=fecha_desde)
        if fecha_hasta:
            instalaciones = instalaciones.filter(fecha_instalacion__date__lte=fecha_hasta)
        
        if reporte_tipo == 'simple':
            headers = ['ID', 'Cliente', 'Cédula', 'Plan', 'Origen', 'Cuadrilla', 'Fecha', 'Estado']
            data = []
            for i in instalaciones:
                origen = "Contrato" if i.asignacion.contrato else "Venta Directa"
                data.append([
                    i.id, i.nombre_cliente, i.cedula_cliente, i.plan, origen,
                    i.asignacion.cuadrilla.nombre if i.asignacion.cuadrilla else 'N/A',
                    i.fecha_instalacion.strftime('%d/%m/%Y') if i.fecha_instalacion else 'No registrada',
                    'Completada' if i.completada else 'Pendiente'
                ])
        else:
            headers = ['ID', 'Cliente', 'Cédula', 'Plan', 'Origen', 'Cuadrilla', 'Fecha', 'Estado', 'Modelo', 'Serial', 'Metros']
            data = []
            for i in instalaciones:
                origen = "Contrato" if i.asignacion.contrato else "Venta Directa"
                data.append([
                    i.id, i.nombre_cliente, i.cedula_cliente, i.plan, origen,
                    i.asignacion.cuadrilla.nombre if i.asignacion.cuadrilla else 'N/A',
                    i.fecha_instalacion.strftime('%d/%m/%Y') if i.fecha_instalacion else 'No registrada',
                    'Completada' if i.completada else 'Pendiente',
                    i.modelo_modem.nombre if i.modelo_modem else 'N/A',
                    i.sn_modem or 'N/A', i.metros_utilizados
                ])
    
    else:  # soportes
        ws = wb.active
        ws.title = "Reporte de Soportes"
        
        soportes = Soporte.objects.all()
        if fecha_desde:
            soportes = soportes.filter(fecha_hora_servicio__date__gte=fecha_desde)
        if fecha_hasta:
            soportes = soportes.filter(fecha_hora_servicio__date__lte=fecha_hasta)
        
        if reporte_tipo == 'simple':
            headers = ['ID', 'Cliente', 'Cédula', 'Tipo', 'Estado', 'Fecha', 'Falla']
            data = [[
                s.id, s.nombre_cliente, s.cedula_cliente, s.get_tipo_display(),
                s.get_estado_display(), s.fecha_hora_servicio.strftime('%d/%m/%Y'),
                s.falla_encontrada[:100] if s.falla_encontrada else 'N/A'
            ] for s in soportes]
        else:
            headers = ['ID', 'Cliente', 'Cédula', 'Tipo', 'Estado', 'Fecha', 'Falla', 'Solución']
            data = [[
                s.id, s.nombre_cliente, s.cedula_cliente, s.get_tipo_display(),
                s.get_estado_display(), s.fecha_hora_servicio.strftime('%d/%m/%Y'),
                s.falla_encontrada[:100] if s.falla_encontrada else 'N/A',
                s.solucion[:100] if s.solucion else 'N/A'
            ] for s in soportes]
    
    # Estilos
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
    
    for col in range(1, len(headers) + 1):
        max_length = max(len(str(headers[col-1])), max([len(str(row[col-1])) for row in data[:100]] or [0]))
        ws.column_dimensions[get_column_letter(col)].width = min(max_length + 2, 50)
    
    filename = f"reporte_{tipo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    
    return response


@login_required
@user_passes_test(es_admin)
def exportar_pdf(request):
    """Exportar datos a PDF"""
    
    import io
    from reportlab.lib.pagesizes import A4, landscape
    
    tipo = request.GET.get('tipo', 'ventas')
    reporte_tipo = request.GET.get('reporte_tipo', 'simple')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    if tipo == 'ventas':
        titulo = "Reporte de Ventas"
        datos = ContratoCliente.objects.filter(estado='COMPLETADO')
        if fecha_desde:
            datos = datos.filter(fecha_creacion__date__gte=fecha_desde)
        if fecha_hasta:
            datos = datos.filter(fecha_creacion__date__lte=fecha_hasta)
        
        if reporte_tipo == 'simple':
            headers = ['ID', 'Cliente', 'Cédula', 'Plan', 'Fecha', 'Vendedor']
            rows = [[
                str(v.id), v.nombre_completo, v.cedula, v.plan_contratado.nombre,
                v.fecha_creacion.strftime('%d/%m/%Y'),
                v.creado_por.get_full_name() or v.creado_por.username if v.creado_por else 'N/A'
            ] for v in datos[:500]]
        else:
            headers = ['ID', 'Cliente', 'Cédula', 'Teléfono', 'Plan', 'Fecha', 'Vendedor']
            rows = [[
                str(v.id), v.nombre_completo, v.cedula, v.telefono_principal,
                v.plan_contratado.nombre, v.fecha_creacion.strftime('%d/%m/%Y'),
                v.creado_por.get_full_name() or v.creado_por.username if v.creado_por else 'N/A'
            ] for v in datos[:500]]
    
    elif tipo == 'instalaciones':
        titulo = "Reporte de Instalaciones"
        datos = Instalacion.objects.all()
        if fecha_desde:
            datos = datos.filter(fecha_instalacion__date__gte=fecha_desde)
        if fecha_hasta:
            datos = datos.filter(fecha_instalacion__date__lte=fecha_hasta)
        
        if reporte_tipo == 'simple':
            headers = ['ID', 'Cliente', 'Cédula', 'Plan', 'Cuadrilla', 'Fecha', 'Estado']
            rows = []
            for i in datos[:500]:
                rows.append([
                    str(i.id), i.nombre_cliente, i.cedula_cliente, i.plan,
                    i.asignacion.cuadrilla.nombre if i.asignacion.cuadrilla else 'N/A',
                    i.fecha_instalacion.strftime('%d/%m/%Y') if i.fecha_instalacion else 'N/A',
                    'Completada' if i.completada else 'Pendiente'
                ])
        else:
            headers = ['ID', 'Cliente', 'Cédula', 'Plan', 'Cuadrilla', 'Fecha', 'Estado', 'Metros']
            rows = []
            for i in datos[:500]:
                rows.append([
                    str(i.id), i.nombre_cliente, i.cedula_cliente, i.plan,
                    i.asignacion.cuadrilla.nombre if i.asignacion.cuadrilla else 'N/A',
                    i.fecha_instalacion.strftime('%d/%m/%Y') if i.fecha_instalacion else 'N/A',
                    'Completada' if i.completada else 'Pendiente', str(i.metros_utilizados)
                ])
    
    else:  # soportes
        titulo = "Reporte de Soportes"
        datos = Soporte.objects.all()
        if fecha_desde:
            datos = datos.filter(fecha_hora_servicio__date__gte=fecha_desde)
        if fecha_hasta:
            datos = datos.filter(fecha_hora_servicio__date__lte=fecha_hasta)
        
        if reporte_tipo == 'simple':
            headers = ['ID', 'Cliente', 'Cédula', 'Tipo', 'Estado', 'Fecha']
            rows = [[
                str(s.id), s.nombre_cliente, s.cedula_cliente, s.get_tipo_display(),
                s.get_estado_display(), s.fecha_hora_servicio.strftime('%d/%m/%Y')
            ] for s in datos[:500]]
        else:
            headers = ['ID', 'Cliente', 'Cédula', 'Tipo', 'Estado', 'Fecha']
            rows = [[
                str(s.id), s.nombre_cliente, s.cedula_cliente, s.get_tipo_display(),
                s.get_estado_display(), s.fecha_hora_servicio.strftime('%d/%m/%Y')
            ] for s in datos[:500]]
    
    # Crear PDF
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
    
    table_data = [headers] + rows
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF6B00')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements = [title, Spacer(1, 12), fecha_paragraph, Spacer(1, 12), table]
    doc.build(elements)
    
    buffer.seek(0)
    filename = f"reporte_{tipo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response