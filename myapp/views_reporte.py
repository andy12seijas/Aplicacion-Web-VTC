from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models.functions import TruncMonth, TruncDate
from .models import ClientePotencial, ContratoCliente, AsignacionContrato, Cuadrilla, Instalacion, Soporte
import json
from django.http import JsonResponse
from django.contrib.auth.models import User, Group 
from django.db.models import Count, Q, Sum, Avg
from django.db.models.functions import TruncMonth
from datetime import datetime, timedelta
import json
@login_required
def reporte_vendedor(request):
    """
    Vista para mostrar reportes y gráficas del vendedor
    """
    
    # Verificar permisos
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_vendedor = request.user.groups.filter(name='Vendedor').exists()
    es_supervisor = request.user.groups.filter(name='Supervisor').exists()
    es_instalador = request.user.groups.filter(name='Instalador').exists()
    
    if not (es_admin or es_vendedor or es_supervisor or es_instalador):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # ========== OBTENER EL VENDEDOR A MOSTRAR ==========
    # Si es ADMIN, puede seleccionar cualquier vendedor
    # Si es VENDEDOR o SUPERVISOR, SOLO ve sus propios datos
    vendedor_id = request.GET.get('vendedor', '')
    
    if es_admin:
        # Admin puede seleccionar cualquier vendedor o ver todos
        if vendedor_id:
            vendedor_filtro_id = vendedor_id
        else:
            vendedor_filtro_id = None
    else:
        # Vendedor o Supervisor: SOLO ven sus propios datos
        vendedor_filtro_id = request.user.id
        vendedor_id = str(request.user.id)  # Para mantener en la URL
    
    # Filtros de fecha para gráficas
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    semana_offset = int(request.GET.get('semana_offset', 0))
    
    # ========== BASE DE DATOS ==========
    if es_admin and vendedor_filtro_id:
        clientes_totales = ClientePotencial.objects.filter(creado_por_id=vendedor_filtro_id)
        contratos_totales = ContratoCliente.objects.filter(creado_por_id=vendedor_filtro_id)
    elif es_admin and not vendedor_filtro_id:
        # Admin viendo todos los vendedores
        clientes_totales = ClientePotencial.objects.all()
        contratos_totales = ContratoCliente.objects.all()
    else:
        # Vendedor o Supervisor viendo sus propios datos
        clientes_totales = ClientePotencial.objects.filter(creado_por=request.user)
        contratos_totales = ContratoCliente.objects.filter(creado_por=request.user)
    
    # ========== ESTADÍSTICAS GENERALES ==========
    total_clientes = clientes_totales.count()
    total_contratos = contratos_totales.count()
    contratos_completados = contratos_totales.filter(estado='COMPLETADO').count()
    contratos_proceso = contratos_totales.filter(estado='EN_PROCESO').count()
    contratos_no_completados = contratos_totales.filter(estado='NO_COMPLETADO').count()
    
    clientes_con_contrato = ContratoCliente.objects.filter(
        cliente_potencial__in=clientes_totales
    ).values('cliente_potencial').distinct().count()
    
    tasa_conversion = (clientes_con_contrato / total_clientes * 100) if total_clientes > 0 else 0
    
    # ========== DATOS PARA GRÁFICAS (CON FILTROS DE FECHA) ==========
    if fecha_desde:
        clientes_graficas = clientes_totales.filter(fecha_registro__gte=fecha_desde)
    else:
        clientes_graficas = clientes_totales
    
    if fecha_hasta:
        clientes_graficas = clientes_graficas.filter(fecha_registro__lte=fecha_hasta)
    
    # 1. Clientes por interés
    interes_data = clientes_graficas.values('interesado').annotate(
        count=Count('id')
    ).order_by('interesado')
    
    interes_labels = []
    interes_values = []
    interes_colors = {'SI': '#10b981', 'TAL_VEZ': '#f59e0b', 'NO': '#ef4444'}
    interes_colors_list = []
    
    for item in interes_data:
        interes_labels.append(dict(ClientePotencial.InteresadoChoices.choices).get(item['interesado'], item['interesado']))
        interes_values.append(item['count'])
        interes_colors_list.append(interes_colors.get(item['interesado'], '#9e9e9e'))
    
    # 2. Distribución de internet
    internet_data = clientes_graficas.values('posee_internet').annotate(count=Count('id'))
    internet_labels = []
    internet_values = []
    for item in internet_data:
        internet_labels.append('Con Internet' if item['posee_internet'] else 'Sin Internet')
        internet_values.append(item['count'])
    
    # 3. Nuevos clientes por mes
    from django.db.models.functions import TruncMonth
    clientes_por_mes = clientes_graficas.annotate(
        mes=TruncMonth('fecha_registro')
    ).values('mes').annotate(
        total=Count('id')
    ).order_by('mes')
    
    clientes_meses_labels = []
    clientes_meses_values = []
    for item in clientes_por_mes:
        if item['mes']:
            clientes_meses_labels.append(item['mes'].strftime('%b %Y'))
            clientes_meses_values.append(item['total'])
    
    # ========== ACUMULATIVO SEMANAL ==========
    # Calcular semana actual (viernes a jueves)
    hoy = timezone.now().date()
    dias_desde_viernes = (hoy.weekday() - 4) % 7
    viernes_actual = hoy - timedelta(days=dias_desde_viernes)
    
    # Aplicar offset para navegar entre semanas
    viernes_seleccionado = viernes_actual - timedelta(weeks=semana_offset)
    jueves_seleccionado = viernes_seleccionado + timedelta(days=6)
    
    from django.db.models import Q
    
    # Contratos COMPLETADOS en la semana (según fecha_actualizacion)
    contratos_completados_semana = ContratoCliente.objects.filter(
        estado='COMPLETADO',
        fecha_completado__date__gte=viernes_seleccionado,
        fecha_completado__date__lte=jueves_seleccionado
    ).select_related('cliente_potencial', 'plan_contratado')
    
    # Contratos EN_PROCESO creados en la semana (NO se han completado aún)
    contratos_en_proceso_semana = contratos_totales.filter(
        estado='EN_PROCESO',
        fecha_creacion__date__gte=viernes_seleccionado,
        fecha_creacion__date__lte=jueves_seleccionado
    ).exclude(
        id__in=contratos_totales.filter(
            estado='COMPLETADO',
            fecha_actualizacion__date__gt=jueves_seleccionado
        ).values_list('id', flat=True)
    ).select_related('cliente_potencial', 'plan_contratado')
    
    # Contratos NO_COMPLETADOS creados en la semana
    contratos_no_completados_semana = contratos_totales.filter(
        estado='NO_COMPLETADO',
        fecha_creacion__date__gte=viernes_seleccionado,
        fecha_creacion__date__lte=jueves_seleccionado
    ).select_related('cliente_potencial', 'plan_contratado')
    
    # Unir todos los contratos de la semana
    contratos_semana = list(contratos_completados_semana) + list(contratos_en_proceso_semana) + list(contratos_no_completados_semana)
    contratos_semana.sort(key=lambda x: x.fecha_actualizacion if x.estado == 'COMPLETADO' else x.fecha_creacion, reverse=True)
    
    # Totales de la semana
    total_contratos_semana = len(contratos_semana)
    completados_semana = contratos_completados_semana.count()
    en_proceso_semana = contratos_en_proceso_semana.count()
    no_completados_semana = contratos_no_completados_semana.count()
    
    # Acumulado hasta la semana
    acumulado_completados = contratos_totales.filter(
        estado='COMPLETADO',
        fecha_actualizacion__date__lte=jueves_seleccionado
    ).count()
    
    acumulado_en_proceso = contratos_totales.filter(
        estado='EN_PROCESO',
        fecha_creacion__date__lte=jueves_seleccionado
    ).exclude(
        id__in=contratos_totales.filter(
            estado='COMPLETADO',
            fecha_actualizacion__date__gt=jueves_seleccionado
        ).values_list('id', flat=True)
    ).count()
    
    acumulado_no_completados = contratos_totales.filter(
        estado='NO_COMPLETADO',
        fecha_creacion__date__lte=jueves_seleccionado
    ).count()
    
    acumulado_total = acumulado_completados + acumulado_en_proceso + acumulado_no_completados
    
    semana_data = {
        'inicio': viernes_seleccionado,
        'fin': jueves_seleccionado,
        'total_contratos': total_contratos_semana,
        'completados': completados_semana,
        'en_proceso': en_proceso_semana,
        'no_completados': no_completados_semana,
        'contratos': contratos_semana,
        'acumulado_completados': acumulado_completados,
        'acumulado_en_proceso': acumulado_en_proceso,
        'acumulado_no_completados': acumulado_no_completados,
        'acumulado_total': acumulado_total,
    }
    
    # ========== LISTA DE VENDEDORES PARA FILTRO (SOLO ADMIN) ==========
    vendedores = []
    if es_admin:
        vendedores = User.objects.filter(
            groups__name__in=['Vendedor', 'Supervisor', 'Instalador']
        ).distinct().order_by('first_name', 'username')
    context = {
        # Estadísticas generales
        'total_clientes': total_clientes,
        'total_contratos': total_contratos,
        'contratos_completados': contratos_completados,
        'contratos_proceso': contratos_proceso,
        'contratos_no_completados': contratos_no_completados,
        'tasa_conversion': round(tasa_conversion, 1),
        'clientes_con_contrato': clientes_con_contrato,
        
        # Semana actual
        'semana_actual': semana_data,
        'es_semana_actual': semana_offset == 0,
        'semana_offset': semana_offset,
        
        # Filtros para gráficas
        'vendedores': vendedores,
        'vendedor_seleccionado': vendedor_id if vendedor_id else '',
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        
        # Gráficas
        'interes_labels': json.dumps(interes_labels),
        'interes_values': json.dumps(interes_values),
        'interes_colors': json.dumps(interes_colors_list),
        'clientes_meses_labels': json.dumps(clientes_meses_labels),
        'clientes_meses_values': json.dumps(clientes_meses_values),
        'internet_labels': json.dumps(internet_labels),
        'internet_values': json.dumps(internet_values),
        
        'es_admin': es_admin,
    }
    
    return render(request, 'Vendedores/reporte_vendedores.html', context)


@login_required
def api_reporte_datos(request):
    """API para obtener datos del reporte en JSON (para actualización dinámica)"""
    
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_vendedor = request.user.groups.filter(name='Vendedor').exists()
    
    if not (es_admin or es_vendedor):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    vendedor_id = request.GET.get('vendedor', request.user.id if not es_admin else '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    # Similar a la vista principal pero devolviendo JSON
    # ... (código similar a la vista principal)
    
    return JsonResponse({'success': True})



@login_required
def reporte_instalador(request):
    """
    Vista para mostrar reportes y gráficas del instalador
    """
    
    # Verificar permisos
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_instalador = request.user.groups.filter(name='Instalador').exists()
    es_supervisor = request.user.groups.filter(name='Supervisor').exists()
    
    if not (es_admin or es_instalador or es_supervisor):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Obtener el instalador actual
    instalador_id = request.GET.get('instalador', request.user.id if not es_admin else '')
    cuadrilla_id = request.GET.get('cuadrilla', '')
    
    # Filtros de fecha para gráficas
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    semana_offset = int(request.GET.get('semana_offset', 0))
    
    # ========== BASE DE DATOS ==========
    # Base para instalaciones
    if es_admin and instalador_id:
        instalaciones_base = Instalacion.objects.filter(instaladores__id=instalador_id)
        soportes_base = Soporte.objects.filter(instaladores__id=instalador_id)
    elif es_instalador:
        instalaciones_base = Instalacion.objects.filter(instaladores=request.user)
        soportes_base = Soporte.objects.filter(instaladores=request.user)
    else:
        instalaciones_base = Instalacion.objects.all()
        soportes_base = Soporte.objects.all()
    
    # Filtrar por cuadrilla si se selecciona
    if cuadrilla_id:
        instalaciones_base = instalaciones_base.filter(asignacion__cuadrilla_id=cuadrilla_id)
        soportes_base = soportes_base.filter(cuadrilla_id=cuadrilla_id)
    
    instalaciones_totales = instalaciones_base
    soportes_totales = soportes_base
    
    # ========== ESTADÍSTICAS GENERALES ==========
    total_instalaciones = instalaciones_totales.count()
    instalaciones_completadas = instalaciones_totales.filter(completada=True).count()
    instalaciones_pendientes = instalaciones_totales.filter(completada=False).count()
    tasa_exito = (instalaciones_completadas / total_instalaciones * 100) if total_instalaciones > 0 else 0
    
    # Soportes
    total_soportes = soportes_totales.count()
    soportes_completados = soportes_totales.filter(estado='COMPLETADO').count()
    soportes_pendientes = soportes_totales.filter(estado='PENDIENTE').count()
    soportes_en_proceso = soportes_totales.filter(estado='EN_PROCESO').count()
    
    # ========== DATOS PARA GRÁFICAS ==========
    # Aplicar filtros de fecha a las gráficas
    if fecha_desde:
        instalaciones_graficas = instalaciones_totales.filter(fecha_creacion__date__gte=fecha_desde)
    else:
        instalaciones_graficas = instalaciones_totales
    
    if fecha_hasta:
        instalaciones_graficas = instalaciones_graficas.filter(fecha_creacion__date__lte=fecha_hasta)
    
    # 1. Instalaciones por estado
    instalaciones_estado_labels = ['Completadas', 'Pendientes']
    instalaciones_estado_values = [
        instalaciones_graficas.filter(completada=True).count(),
        instalaciones_graficas.filter(completada=False).count()
    ]
    instalaciones_estado_colors = ['#10b981', '#f59e0b']
    
    # 2. Instalaciones por mes
    hoy = timezone.now().date()
    fecha_12_meses = hoy - timedelta(days=365)
    
    instalaciones_por_mes = instalaciones_totales.filter(
        fecha_creacion__date__gte=fecha_12_meses
    ).annotate(
        mes=TruncMonth('fecha_creacion')
    ).values('mes').annotate(
        total=Count('id'),
        completadas=Count('id', filter=Q(completada=True))
    ).order_by('mes')
    
    meses_labels = []
    instalaciones_totales_mes = []
    instalaciones_completadas_mes = []
    
    for item in instalaciones_por_mes:
        if item['mes']:
            meses_labels.append(item['mes'].strftime('%b %Y'))
            instalaciones_totales_mes.append(item['total'])
            instalaciones_completadas_mes.append(item['completadas'])
    
    # 3. Soportes por tipo (obtener tipo desde el ticket asociado)
    soportes_por_tipo = []
    tipo_dict = {}
    
    for sop in soportes_totales:
        try:
            tipo = sop.asignacion.ticket.tipo_soporte
            tipo_dict[tipo] = tipo_dict.get(tipo, 0) + 1
        except:
            pass
    
    soportes_tipo_labels = []
    soportes_tipo_values = []
    soportes_tipo_colors = {'MUDANZA': '#3b82f6', 'RETIRO': '#f59e0b', 'RECABLEADO': '#8b5cf6', 'SOPORTE': '#9e9e9e'}
    soportes_tipo_colors_list = []
    
    tipo_display = {
        'MUDANZA': 'Mudanza',
        'RETIRO': 'Retiro',
        'RECABLEADO': 'Recableado',
        'SOPORTE': 'Soporte Técnico'
    }
    
    for tipo, count in tipo_dict.items():
        soportes_tipo_labels.append(tipo_display.get(tipo, tipo))
        soportes_tipo_values.append(count)
        soportes_tipo_colors_list.append(soportes_tipo_colors.get(tipo, '#9e9e9e'))
    
    # 4. Soportes por estado
    soportes_estado_labels = ['Completados', 'Pendientes', 'En Proceso']
    soportes_estado_values = [
        soportes_totales.filter(estado='COMPLETADO').count(),
        soportes_totales.filter(estado='PENDIENTE').count(),
        soportes_totales.filter(estado='EN_PROCESO').count()
    ]
    soportes_estado_colors = ['#10b981', '#f59e0b', '#3b82f6']
    
    # 5. Materiales utilizados (promedio)
    instalaciones_completadas_filter = instalaciones_totales.filter(completada=True)
    
    # Calcular promedio de metros manualmente
    total_metros = 0
    total_instalaciones_metros = 0
    
    for inst in instalaciones_completadas_filter:
        if inst.inicio_fibra is not None and inst.final_fibra is not None:
            total_metros += abs(inst.final_fibra - inst.inicio_fibra)
            total_instalaciones_metros += 1
    
    avg_metros = total_metros / total_instalaciones_metros if total_instalaciones_metros > 0 else 0
    
    materiales = {
        'avg_conectores': instalaciones_completadas_filter.aggregate(Avg('conectores'))['conectores__avg'] or 0,
        'avg_rosetas': instalaciones_completadas_filter.aggregate(Avg('rosetas'))['rosetas__avg'] or 0,
        'avg_patch_cord': instalaciones_completadas_filter.aggregate(Avg('patch_cord'))['patch_cord__avg'] or 0,
        'avg_tensores': instalaciones_completadas_filter.aggregate(Avg('tensores'))['tensores__avg'] or 0,
        'avg_metros': avg_metros,
    }
    
    # ========== ACUMULATIVO SEMANAL ==========
    # Calcular semana actual (viernes a jueves)
    dias_desde_viernes = (hoy.weekday() - 4) % 7
    viernes_actual = hoy - timedelta(days=dias_desde_viernes)
    
    # Aplicar offset para navegar entre semanas
    viernes_seleccionado = viernes_actual - timedelta(weeks=semana_offset)
    jueves_seleccionado = viernes_seleccionado + timedelta(days=6)
    
    # Instalaciones COMPLETADAS en la semana
    instalaciones_completadas_semana = instalaciones_totales.filter(
        completada=True,
        fecha_instalacion__date__gte=viernes_seleccionado,
        fecha_instalacion__date__lte=jueves_seleccionado
    ).select_related('asignacion__cuadrilla', 'asignacion__contrato__cliente_potencial')
    
    # Instalaciones PENDIENTES creadas en la semana
    instalaciones_pendientes_semana = instalaciones_totales.filter(
        completada=False,
        fecha_creacion__date__gte=viernes_seleccionado,
        fecha_creacion__date__lte=jueves_seleccionado
    ).exclude(
        id__in=instalaciones_totales.filter(
            completada=True,
            fecha_instalacion__date__gt=jueves_seleccionado
        ).values_list('id', flat=True)
    ).select_related('asignacion__cuadrilla', 'asignacion__contrato__cliente_potencial')
    
    # Soportes COMPLETADOS en la semana
    soportes_completados_semana = soportes_totales.filter(
        estado='COMPLETADO',
        fecha_actualizacion__date__gte=viernes_seleccionado,
        fecha_actualizacion__date__lte=jueves_seleccionado
    ).select_related('asignacion__ticket', 'cuadrilla')
    
    # Soportes PENDIENTES creados en la semana
    soportes_pendientes_semana = soportes_totales.filter(
        estado='PENDIENTE',
        fecha_creacion__date__gte=viernes_seleccionado,
        fecha_creacion__date__lte=jueves_seleccionado
    ).exclude(
        id__in=soportes_totales.filter(
            estado='COMPLETADO',
            fecha_actualizacion__date__gt=jueves_seleccionado
        ).values_list('id', flat=True)
    ).select_related('asignacion__ticket', 'cuadrilla')
    
    # Unir todas las instalaciones de la semana
    instalaciones_semana = list(instalaciones_completadas_semana) + list(instalaciones_pendientes_semana)
    instalaciones_semana.sort(key=lambda x: x.fecha_instalacion if x.completada else x.fecha_creacion, reverse=True)
    
    # Unir todos los soportes de la semana
    soportes_semana = list(soportes_completados_semana) + list(soportes_pendientes_semana)
    soportes_semana.sort(key=lambda x: x.fecha_actualizacion if x.estado == 'COMPLETADO' else x.fecha_creacion, reverse=True)
    
    # Totales de la semana
    total_instalaciones_semana = len(instalaciones_semana)
    completadas_semana = instalaciones_completadas_semana.count()
    pendientes_semana = instalaciones_pendientes_semana.count()
    
    total_soportes_semana = len(soportes_semana)
    soportes_completados_semana_count = soportes_completados_semana.count()
    soportes_pendientes_semana_count = soportes_pendientes_semana.count()
    
    # Acumulado hasta la semana
    acumulado_instalaciones_completadas = instalaciones_totales.filter(
        completada=True,
        fecha_instalacion__date__lte=jueves_seleccionado
    ).count()
    
    acumulado_instalaciones_pendientes = instalaciones_totales.filter(
        completada=False,
        fecha_creacion__date__lte=jueves_seleccionado
    ).exclude(
        id__in=instalaciones_totales.filter(
            completada=True,
            fecha_instalacion__date__gt=jueves_seleccionado
        ).values_list('id', flat=True)
    ).count()
    
    acumulado_instalaciones_total = acumulado_instalaciones_completadas + acumulado_instalaciones_pendientes
    
    acumulado_soportes_completados = soportes_totales.filter(
        estado='COMPLETADO',
        fecha_actualizacion__date__lte=jueves_seleccionado
    ).count()
    
    acumulado_soportes_pendientes = soportes_totales.filter(
        estado='PENDIENTE',
        fecha_creacion__date__lte=jueves_seleccionado
    ).exclude(
        id__in=soportes_totales.filter(
            estado='COMPLETADO',
            fecha_actualizacion__date__gt=jueves_seleccionado
        ).values_list('id', flat=True)
    ).count()
    
    acumulado_soportes_total = acumulado_soportes_completados + acumulado_soportes_pendientes
    
    semana_data = {
        'inicio': viernes_seleccionado,
        'fin': jueves_seleccionado,
        'total_instalaciones': total_instalaciones_semana,
        'instalaciones_completadas': completadas_semana,
        'instalaciones_pendientes': pendientes_semana,
        'instalaciones': instalaciones_semana,
        'acumulado_instalaciones_completadas': acumulado_instalaciones_completadas,
        'acumulado_instalaciones_pendientes': acumulado_instalaciones_pendientes,
        'acumulado_instalaciones_total': acumulado_instalaciones_total,
        'total_soportes': total_soportes_semana,
        'soportes_completados': soportes_completados_semana_count,
        'soportes_pendientes': soportes_pendientes_semana_count,
        'soportes': soportes_semana,
        'acumulado_soportes_completados': acumulado_soportes_completados,
        'acumulado_soportes_pendientes': acumulado_soportes_pendientes,
        'acumulado_soportes_total': acumulado_soportes_total,
    }
    
    # ========== TABLAS ==========
    ultimas_instalaciones = instalaciones_totales.select_related(
        'asignacion__cuadrilla', 'asignacion__contrato__cliente_potencial'
    ).order_by('-fecha_creacion')[:10]
    
    ultimos_soportes = soportes_totales.select_related(
        'asignacion__ticket', 'cuadrilla'
    ).order_by('-fecha_creacion')[:10]
    
    # ========== OBTENER LISTAS PARA FILTROS ==========
    instaladores_lista = []
    if es_admin:
        instaladores_lista = User.objects.filter(groups__name='Instalador').distinct().order_by('first_name', 'username')
    
    # Obtener cuadrillas para el filtro
    cuadrillas_lista = Cuadrilla.objects.filter(activo=True).order_by('nombre')
    
    context = {
        # Estadísticas generales
        'total_instalaciones': total_instalaciones,
        'instalaciones_completadas': instalaciones_completadas,
        'instalaciones_pendientes': instalaciones_pendientes,
        'tasa_exito': round(tasa_exito, 1),
        'total_soportes': total_soportes,
        'soportes_completados': soportes_completados,
        'soportes_pendientes': soportes_pendientes,
        'soportes_en_proceso': soportes_en_proceso,
        
        # Semana actual
        'semana_actual': semana_data,
        'es_semana_actual': semana_offset == 0,
        'semana_offset': semana_offset,
        
        # Gráficas
        'instalaciones_estado_labels': json.dumps(instalaciones_estado_labels),
        'instalaciones_estado_values': json.dumps(instalaciones_estado_values),
        'instalaciones_estado_colors': json.dumps(instalaciones_estado_colors),
        
        'meses_labels': json.dumps(meses_labels),
        'instalaciones_totales_mes': json.dumps(instalaciones_totales_mes),
        'instalaciones_completadas_mes': json.dumps(instalaciones_completadas_mes),
        
        'soportes_tipo_labels': json.dumps(soportes_tipo_labels),
        'soportes_tipo_values': json.dumps(soportes_tipo_values),
        'soportes_tipo_colors': json.dumps(soportes_tipo_colors_list),
        
        'soportes_estado_labels': json.dumps(soportes_estado_labels),
        'soportes_estado_values': json.dumps(soportes_estado_values),
        'soportes_estado_colors': json.dumps(soportes_estado_colors),
        
        'materiales': materiales,
        
        # Tablas
        'ultimas_instalaciones': ultimas_instalaciones,
        'ultimos_soportes': ultimos_soportes,
        
        # Filtros
        'instaladores': instaladores_lista,
        'cuadrillas': cuadrillas_lista,
        'instalador_seleccionado': instalador_id,
        'cuadrilla_seleccionada': cuadrilla_id,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'es_admin': es_admin,
    }
    
    return render(request, 'Instaladores/reporte_instalador.html', context)