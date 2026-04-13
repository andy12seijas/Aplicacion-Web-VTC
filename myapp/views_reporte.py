from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models.functions import TruncMonth, TruncDate
from .models import ClientePotencial, ContratoCliente, AsignacionContrato, Instalacion
import json
from django.http import JsonResponse
from django.contrib.auth.models import User, Group 

@login_required
def reporte_vendedor(request):
    """
    Vista para mostrar reportes y gráficas del vendedor
    """
    
    # Verificar permisos
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_vendedor = request.user.groups.filter(name='Vendedor').exists()
    es_supervisor = request.user.groups.filter(name='Supervisor').exists()
    
    if not (es_admin or es_vendedor or es_supervisor):
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
    contratos_completados_semana = contratos_totales.filter(
        estado='COMPLETADO',
        fecha_actualizacion__date__gte=viernes_seleccionado,
        fecha_actualizacion__date__lte=jueves_seleccionado
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
        vendedores = User.objects.filter(groups__name='Vendedor').distinct().order_by('first_name', 'username')
    
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