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
    
    # Verificar que el usuario sea vendedor o administrador
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_vendedor = request.user.groups.filter(name='Vendedor').exists()
    es_instalador = request.user.groups.filter(name='Instalador').exists()
    
    if not (es_admin or es_vendedor or es_instalador):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Obtener el vendedor actual (si no es admin, solo ve sus datos)
    vendedor_id = request.GET.get('vendedor', request.user.id if not es_admin else '')
    
    # Obtener parámetros de filtro
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    periodo = request.GET.get('periodo', 'mes')  # mes, trimestre, año
    
    # Calcular fechas según el período seleccionado
    hoy = timezone.now().date()
    
    if fecha_desde and fecha_hasta:
        fecha_inicio = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    else:
        if periodo == 'mes':
            fecha_inicio = hoy.replace(day=1)
            fecha_fin = hoy
        elif periodo == 'trimestre':
            trimestre = (hoy.month - 1) // 3
            fecha_inicio = hoy.replace(month=trimestre * 3 + 1, day=1)
            fecha_fin = hoy
        else:  # año
            fecha_inicio = hoy.replace(month=1, day=1)
            fecha_fin = hoy
    
    # Base de clientes
    if es_admin and vendedor_id:
        clientes = ClientePotencial.objects.filter(creado_por_id=vendedor_id)
        contratos = ContratoCliente.objects.filter(creado_por_id=vendedor_id)
    elif es_vendedor:
        clientes = ClientePotencial.objects.filter(creado_por=request.user)
        contratos = ContratoCliente.objects.filter(creado_por=request.user)
    else:
        clientes = ClientePotencial.objects.all()
        contratos = ContratoCliente.objects.all()
    
    # Aplicar filtros de fecha
    if fecha_desde:
        clientes = clientes.filter(fecha_registro__gte=fecha_desde)
        contratos = contratos.filter(fecha_creacion__date__gte=fecha_desde)
    if fecha_hasta:
        clientes = clientes.filter(fecha_registro__lte=fecha_hasta)
        contratos = contratos.filter(fecha_creacion__date__lte=fecha_hasta)
    
    # ========== ESTADÍSTICAS GENERALES ==========
    total_clientes = clientes.count()
    clientes_mes = clientes.filter(fecha_registro__month=hoy.month).count()
    clientes_semana = clientes.filter(fecha_registro__gte=hoy - timedelta(days=7)).count()
    
    # Contratos por estado
    total_contratos = contratos.count()
    contratos_proceso = contratos.filter(estado='EN_PROCESO').count()
    contratos_completados = contratos.filter(estado='COMPLETADO').count()
    contratos_no_completados = contratos.filter(estado='NO_COMPLETADO').count()
    
    # Tasa de conversión (clientes que se convirtieron en contrato)
    clientes_con_contrato = ContratoCliente.objects.filter(
        cliente_potencial__in=clientes
    ).values('cliente_potencial').distinct().count()
    
    tasa_conversion = (clientes_con_contrato / total_clientes * 100) if total_clientes > 0 else 0
    
    # ========== DATOS PARA GRÁFICAS ==========
    
    # 1. Clientes por interés
    interes_data = clientes.values('interesado').annotate(
        count=Count('id')
    ).order_by('interesado')
    
    interes_labels = []
    interes_values = []
    interes_colors = {
        'SI': '#4caf50',
        'TAL_VEZ': '#ff9800',
        'NO': '#f44336'
    }
    
    for item in interes_data:
        interes_labels.append(dict(ClientePotencial.InteresadoChoices.choices).get(item['interesado'], item['interesado']))
        interes_values.append(item['count'])
    
    # 2. Contratos por mes (últimos 12 meses)
    fecha_12_meses = hoy - timedelta(days=365)
    contratos_por_mes = contratos.filter(
        fecha_creacion__date__gte=fecha_12_meses
    ).annotate(
        mes=TruncMonth('fecha_creacion')
    ).values('mes').annotate(
        total=Count('id'),
        completados=Count('id', filter=Q(estado='COMPLETADO')),
        en_proceso=Count('id', filter=Q(estado='EN_PROCESO'))
    ).order_by('mes')
    
    meses_labels = []
    meses_totales = []
    meses_completados = []
    
    for item in contratos_por_mes:
        meses_labels.append(item['mes'].strftime('%b %Y'))
        meses_totales.append(item['total'])
        meses_completados.append(item['completados'])
    
    # 3. Clientes registrados por mes
    clientes_por_mes = clientes.filter(
        fecha_registro__gte=fecha_12_meses
    ).annotate(
        mes=TruncMonth('fecha_registro')
    ).values('mes').annotate(
        total=Count('id')
    ).order_by('mes')
    
    clientes_meses_labels = []
    clientes_meses_values = []
    
    for item in clientes_por_mes:
        clientes_meses_labels.append(item['mes'].strftime('%b %Y'))
        clientes_meses_values.append(item['total'])
    
    # 4. Top 5 vendedores (solo para admin)
    top_vendedores = []
    if es_admin:
        top_vendedores_data = ClientePotencial.objects.values(
            'creado_por__username',
            'creado_por__first_name',
            'creado_por__last_name'
        ).annotate(
            total_clientes=Count('id'),
            total_contratos=Count('contratos'),
            contratos_completados=Count('contratos', filter=Q(contratos__estado='COMPLETADO'))
        ).order_by('-total_clientes')[:5]
        
        for v in top_vendedores_data:
            top_vendedores.append({
                'nombre': v['creado_por__first_name'] or v['creado_por__username'],
                'clientes': v['total_clientes'],
                'contratos': v['total_contratos'],
                'completados': v['contratos_completados']
            })
    
    # 5. Distribución de internet
    internet_data = clientes.values('posee_internet').annotate(
        count=Count('id')
    )
    
    internet_labels = []
    internet_values = []
    for item in internet_data:
        internet_labels.append('Con Internet' if item['posee_internet'] else 'Sin Internet')
        internet_values.append(item['count'])
    
    # 6. Últimos 10 clientes
    ultimos_clientes = clientes.order_by('-fecha_registro')[:10]
    
    # 7. Últimos 10 contratos
    ultimos_contratos = contratos.select_related('cliente_potencial').order_by('-fecha_creacion')[:10]
    
    # 8. Instalaciones completadas por mes
    instalaciones_por_mes = Instalacion.objects.filter(
        completada=True,
        fecha_instalacion__date__gte=fecha_12_meses
    ).annotate(
        mes=TruncMonth('fecha_instalacion')
    ).values('mes').annotate(
        total=Count('id')
    ).order_by('mes')
    
    instalaciones_labels = []
    instalaciones_values = []
    
    for item in instalaciones_por_mes:
        instalaciones_labels.append(item['mes'].strftime('%b %Y'))
        instalaciones_values.append(item['total'])
    
    # Obtener lista de vendedores para el filtro (solo admin)
    vendedores = []
    if es_admin:
        vendedores = User.objects.filter(groups__name='Vendedor').distinct().order_by('first_name', 'username')
    
    context = {
        # Estadísticas generales
        'total_clientes': total_clientes,
        'clientes_mes': clientes_mes,
        'clientes_semana': clientes_semana,
        'total_contratos': total_contratos,
        'contratos_proceso': contratos_proceso,
        'contratos_completados': contratos_completados,
        'contratos_no_completados': contratos_no_completados,
        'tasa_conversion': round(tasa_conversion, 1),
        
        # Datos para gráficas (JSON para JavaScript)
        'interes_labels': json.dumps(interes_labels),
        'interes_values': json.dumps(interes_values),
        'interes_colors': json.dumps([interes_colors.get(k, '#9e9e9e') for k in [item['interesado'] for item in interes_data]]),
        
        'meses_labels': json.dumps(meses_labels),
        'meses_totales': json.dumps(meses_totales),
        'meses_completados': json.dumps(meses_completados),
        
        'clientes_meses_labels': json.dumps(clientes_meses_labels),
        'clientes_meses_values': json.dumps(clientes_meses_values),
        
        'internet_labels': json.dumps(internet_labels),
        'internet_values': json.dumps(internet_values),
        
        'instalaciones_labels': json.dumps(instalaciones_labels),
        'instalaciones_values': json.dumps(instalaciones_values),
        
        # Tablas
        'ultimos_clientes': ultimos_clientes,
        'ultimos_contratos': ultimos_contratos,
        'top_vendedores': top_vendedores,
        
        # Filtros
        'vendedores': vendedores,
        'vendedor_seleccionado': vendedor_id,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'periodo': periodo,
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