import json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum, Avg, F
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth.models import User, Group
from django.db.models.functions import TruncDate, TruncWeek
from .models import (
    ClienteExterno, ContratoCliente, ClientePotencial, Cuadrilla, AsignacionContrato,
    Instalacion, RegistroLlamada, Soporte, VentaDirecta, NominaVendedor, Plan
)

def es_vendedor(user):
    return user.groups.filter(name='Vendedor').exists() or user.is_superuser

def es_instalador(user):
    return user.groups.filter(name='Instalador').exists() or user.is_superuser

def es_administrador(user):
    return user.groups.filter(name='Administrador').exists() or user.is_superuser

@login_required
def dashboard(request):
    user = request.user
    
    # Verificar rol del usuario
    if user.is_superuser or user.groups.filter(name='Administrador').exists():
        return dashboard_administrador(request)
    elif user.groups.filter(name='Vendedor').exists():
        return dashboard_vendedor(request)
    elif user.groups.filter(name='Instalador').exists():
        return dashboard_instalador(request)
    elif user.groups.filter(name='Supervisor').exists():
        return dashboard_supervisor(request)
    elif user.groups.filter(name='Call Center').exists():
        return dashboard_callcenter(request)
    else:
        # Perfil sin rol específico
        return dashboard_general(request)

# ==================== DASHBOARD VENDEDOR ====================
def dashboard_vendedor(request):
    user = request.user
    
    # Fechas para filtros
    hoy = timezone.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    
    # Contratos del vendedor
    contratos = ContratoCliente.objects.filter(creado_por=user)
    
    # Estadísticas
    total_contratos = contratos.count()
    contratos_completados = contratos.filter(estado=ContratoCliente.EstadoContrato.COMPLETADO).count()
    contratos_proceso = contratos.filter(estado=ContratoCliente.EstadoContrato.EN_PROCESO).count()
    contratos_no_completados = contratos.filter(estado=ContratoCliente.EstadoContrato.NO_COMPLETADO).count()
    
    # Contratos por mes (últimos 6 meses)
    meses = []
    contratos_por_mes = []
    for i in range(5, -1, -1):
        fecha_inicio = hoy.replace(day=1) - timedelta(days=30*i)
        fecha_fin = (fecha_inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        
        conteo = contratos.filter(fecha_creacion__date__gte=fecha_inicio, fecha_creacion__date__lte=fecha_fin).count()
        meses.append(fecha_inicio.strftime('%b'))
        contratos_por_mes.append(conteo)
    
    # Contratos recientes
    contratos_recientes = contratos.select_related('cliente_potencial', 'plan_contratado').order_by('-fecha_creacion')[:10]
    
    # Clientes potenciales del vendedor
    clientes_potenciales = ClientePotencial.objects.filter(creado_por=user)
    
    # Planes más contratados
    planes_populares = contratos.values('plan_contratado__nombre').annotate(
        total=Count('id')
    ).order_by('-total')[:5]
    
    # Progreso de la semana
    contratos_semana = contratos.filter(
        fecha_creacion__date__gte=inicio_semana,
        fecha_creacion__date__lte=fin_semana,
        estado=ContratoCliente.EstadoContrato.COMPLETADO
    ).count()
    
    # Obtener o crear nómina de la semana actual
    nomina, _ = NominaVendedor.objects.get_or_create(
        vendedor=user,
        semana_inicio=inicio_semana,
        defaults={'semana_fin': fin_semana, 'total_contratos': contratos_semana}
    )
    if nomina.total_contratos != contratos_semana:
        nomina.total_contratos = contratos_semana
        nomina.save()
    
    context = {
        'rol': 'vendedor',
        'total_contratos': total_contratos,
        'contratos_completados': contratos_completados,
        'contratos_proceso': contratos_proceso,
        'contratos_no_completados': contratos_no_completados,
        'porcentaje_completado': (contratos_completados / total_contratos * 100) if total_contratos > 0 else 0,
        'contratos_por_mes': contratos_por_mes,
        'meses': meses,
        'contratos_recientes': contratos_recientes,
        'clientes_potenciales_count': clientes_potenciales.count(),
        'planes_populares': planes_populares,
        'nomina_semana': nomina,
        'contratos_semana': contratos_semana,
    }
    
    return render(request, 'Inicio_De_Sesion/dashboard.html', context)


# ==================== DASHBOARD INSTALADOR ====================
# ==================== DASHBOARD INSTALADOR ====================
# ==================== DASHBOARD INSTALADOR ====================
def dashboard_instalador(request):
    user = request.user
    
    # Obtener perfil del usuario
    perfil = user.perfil if hasattr(user, 'perfil') else None
    
    # Asignaciones pendientes del instalador (a través de cuadrilla)
    cuadrillas = Cuadrilla.objects.filter(instaladores__usuario=user)
    asignaciones = AsignacionContrato.objects.filter(
        cuadrilla__in=cuadrillas,
        activo=True
    )
    
    # Instalaciones realizadas por este instalador
    instalaciones_realizadas = Instalacion.objects.filter(instaladores=user)
    
    # Soportes realizados
    soportes_realizados = Soporte.objects.filter(instaladores=user)
    
    # Estadísticas
    total_asignaciones = asignaciones.count()
    instalaciones_completadas = instalaciones_realizadas.filter(completada=True).count()
    instalaciones_pendientes = total_asignaciones - instalaciones_completadas
    
    # Instalaciones por mes
    hoy = timezone.now().date()
    meses = []
    instalaciones_por_mes = []
    for i in range(5, -1, -1):
        fecha_inicio = hoy.replace(day=1) - timedelta(days=30*i)
        fecha_fin = (fecha_inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        
        conteo = instalaciones_realizadas.filter(
            fecha_instalacion__date__gte=fecha_inicio,
            fecha_instalacion__date__lte=fecha_fin,
            completada=True
        ).count()
        meses.append(fecha_inicio.strftime('%b'))
        instalaciones_por_mes.append(conteo)
    
    # Próximas asignaciones (sin instalación aún)
    asignaciones_ids = asignaciones.values_list('id', flat=True)
    instaladas_ids = Instalacion.objects.filter(asignacion__in=asignaciones).values_list('asignacion_id', flat=True)
    pendientes_ids = [aid for aid in asignaciones_ids if aid not in instaladas_ids]
    asignaciones_pendientes = AsignacionContrato.objects.filter(id__in=pendientes_ids).select_related(
        'contrato__cliente_potencial', 'venta_directa', 'cuadrilla'
    )[:10]
    
    # Últimas instalaciones realizadas
    ultimas_instalaciones = instalaciones_realizadas.select_related(
        'asignacion__contrato__cliente_potencial'
    ).order_by('-fecha_instalacion')[:10]
    
    # Soportes recientes
    soportes_recientes = soportes_realizados.select_related(
        'asignacion__ticket', 'cuadrilla'
    ).order_by('-fecha_creacion')[:5]
    
    # Para cada soporte, agregar el tipo display manualmente
    for soporte in soportes_recientes:
        try:
            if soporte.asignacion and soporte.asignacion.ticket:
                soporte.tipo_display = soporte.asignacion.ticket.get_tipo_soporte_display()
            else:
                soporte.tipo_display = "Soporte"
        except:
            soporte.tipo_display = "Soporte"
    
    # ========== MATERIALES UTILIZADOS (CORREGIDO - sin usar propiedad) ==========
    # Calcular promedios directamente con agregación de Django sobre campos reales
    from django.db.models import Avg, F
    
    instalaciones_completadas_filter = instalaciones_realizadas.filter(completada=True)
    
    # Promedio de materiales usando los campos reales
    avg_conectores = instalaciones_completadas_filter.aggregate(Avg('conectores'))['conectores__avg'] or 0
    avg_rosetas = instalaciones_completadas_filter.aggregate(Avg('rosetas'))['rosetas__avg'] or 0
    avg_patch_cord = instalaciones_completadas_filter.aggregate(Avg('patch_cord'))['patch_cord__avg'] or 0
    avg_tensores = instalaciones_completadas_filter.aggregate(Avg('tensores'))['tensores__avg'] or 0
    
    # Para los metros, calcular manualmente porque es una propiedad (no campo de BD)
    total_metros = 0
    count_instalaciones = 0
    for inst in instalaciones_completadas_filter:
        if inst.inicio_fibra is not None and inst.final_fibra is not None:
            total_metros += abs(inst.final_fibra - inst.inicio_fibra)
            count_instalaciones += 1
    
    avg_metros = total_metros / count_instalaciones if count_instalaciones > 0 else 0
    
    materiales = {
        'avg_conectores': avg_conectores,
        'avg_rosetas': avg_rosetas,
        'avg_patch_cord': avg_patch_cord,
        'avg_tensores': avg_tensores,
        'avg_metros': avg_metros,
    }
    
    # Posición en el ranking de instaladores (si hay más de uno)
    ranking_posicion = None
    ranking_total = None
    if perfil:
        todos_instaladores = User.objects.filter(groups__name='Instalador')
        ranking = []
        for inst in todos_instaladores:
            count = Instalacion.objects.filter(instaladores=inst, completada=True).count()
            ranking.append((inst, count))
        ranking.sort(key=lambda x: x[1], reverse=True)
        
        for idx, (inst, count) in enumerate(ranking, 1):
            if inst == user:
                ranking_posicion = idx
                ranking_total = len(ranking)
                break
    
    context = {
        'rol': 'instalador',
        'total_asignaciones': total_asignaciones,
        'instalaciones_completadas': instalaciones_completadas,
        'instalaciones_pendientes': instalaciones_pendientes,
        'porcentaje_completado': (instalaciones_completadas / total_asignaciones * 100) if total_asignaciones > 0 else 0,
        'soportes_realizados_count': soportes_realizados.count(),
        'instalaciones_por_mes': instalaciones_por_mes,
        'meses': meses,
        'asignaciones_pendientes': asignaciones_pendientes,
        'ultimas_instalaciones': ultimas_instalaciones,
        'soportes_recientes': soportes_recientes,
        'materiales': materiales,
        'ranking_posicion': ranking_posicion,
        'ranking_total': ranking_total,
    }
    
    return render(request, 'Inicio_De_Sesion/dashboard.html', context)

# ==================== DASHBOARD ADMINISTRADOR ====================
# ==================== DASHBOARD ADMINISTRADOR ====================
def dashboard_administrador(request):
    user = request.user
    
    hoy = timezone.now().date()
    
    # ========== CLIENTES POTENCIALES ==========
    total_clientes_potenciales = ClientePotencial.objects.count()
    
    # Clientes por interés
    clientes_interes = ClientePotencial.objects.values('interesado').annotate(
        count=Count('id')
    ).order_by('interesado')
    
    interes_labels = []
    interes_values = []
    for item in clientes_interes:
        interes_labels.append(dict(ClientePotencial.InteresadoChoices.choices).get(item['interesado'], item['interesado']))
        interes_values.append(item['count'])
    
    # ========== CONTRATOS ==========
    total_contratos = ContratoCliente.objects.count()
    contratos_completados = ContratoCliente.objects.filter(estado=ContratoCliente.EstadoContrato.COMPLETADO).count()
    contratos_proceso = ContratoCliente.objects.filter(estado=ContratoCliente.EstadoContrato.EN_PROCESO).count()
    contratos_no_completados = ContratoCliente.objects.filter(estado=ContratoCliente.EstadoContrato.NO_COMPLETADO).count()
    
    # Datos para gráfica de torta de contratos
    contratos_estado_labels = ['Completados', 'En Proceso', 'No Completados']
    contratos_estado_values = [contratos_completados, contratos_proceso, contratos_no_completados]
    contratos_estado_colors = ['#10b981', '#f59e0b', '#ef4444']
    
    # ========== INSTALACIONES ==========
    total_instalaciones = Instalacion.objects.count()
    instalaciones_completadas = Instalacion.objects.filter(completada=True).count()
    instalaciones_pendientes = total_instalaciones - instalaciones_completadas
    
    # Datos para gráfica de torta de instalaciones
    instalaciones_labels = ['Completadas', 'Pendientes']
    instalaciones_values = [instalaciones_completadas, instalaciones_pendientes]
    instalaciones_colors = ['#10b981', '#f59e0b']
    
    # ========== SOPORTES (CORREGIDO) ==========
    total_soportes = Soporte.objects.count()
    soportes_pendientes = Soporte.objects.filter(estado='PENDIENTE').count()
    soportes_proceso = Soporte.objects.filter(estado='EN_PROCESO').count()
    soportes_completados = Soporte.objects.filter(estado='COMPLETADO').count()
    soportes_no_completados = Soporte.objects.filter(estado='NO_COMPLETADO').count()
    
    # Soportes por tipo (desde el ticket asociado)
    soportes_tipo = Soporte.objects.exclude(asignacion__isnull=True).exclude(asignacion__ticket__isnull=True).values('asignacion__ticket__tipo_soporte').annotate(
        count=Count('id')
    ).order_by('-count')
    
    soportes_tipo_labels = []
    soportes_tipo_values = []
    soportes_tipo_colors = []
    
    tipo_colors = {
        'MUDANZA': '#3b82f6',
        'RETIRO': '#f59e0b', 
        'RECABLEADO': '#8b5cf6',
        'SOPORTE': '#9e9e9e'
    }
    
    tipo_display = {
        'MUDANZA': 'Mudanza',
        'RETIRO': 'Retiro',
        'RECABLEADO': 'Recableado',
        'SOPORTE': 'Soporte Técnico'
    }
    
    for item in soportes_tipo:
        tipo = item['asignacion__ticket__tipo_soporte']
        if tipo:
            soportes_tipo_labels.append(tipo_display.get(tipo, tipo))
            soportes_tipo_values.append(item['count'])
            soportes_tipo_colors.append(tipo_colors.get(tipo, '#9e9e9e'))
    
    # Si no hay soportes, mostrar datos vacíos
    if not soportes_tipo_labels:
        soportes_tipo_labels = ['Sin datos']
        soportes_tipo_values = [0]
        soportes_tipo_colors = ['#e5e7eb']
    
    # Asignaciones pendientes
    asignaciones_pendientes = AsignacionContrato.objects.filter(
        activo=True
    ).exclude(
        id__in=Instalacion.objects.values_list('asignacion_id', flat=True)
    ).count()
    
    # ========== ÚLTIMOS CONTRATOS ==========
    ultimos_contratos = ContratoCliente.objects.select_related(
        'cliente_potencial', 'plan_contratado', 'creado_por'
    ).order_by('-fecha_creacion')[:10]
    
    # ========== TOP VENDEDORES ==========
    top_vendedores = User.objects.filter(groups__name='Vendedor').annotate(
        total_contratos=Count('contratos_creados', filter=Q(contratos_creados__estado=ContratoCliente.EstadoContrato.COMPLETADO))
    ).order_by('-total_contratos')[:5]
    
    # ========== ÚLTIMAS INSTALACIONES ==========
    ultimas_instalaciones = Instalacion.objects.filter(
        completada=True
    ).select_related('asignacion__cuadrilla', 'asignacion__contrato__cliente_potencial').order_by('-fecha_instalacion')[:5]
    
    # ========== ÚLTIMOS SOPORTES ==========
    ultimos_soportes = Soporte.objects.filter(
        estado='COMPLETADO'
    ).select_related('asignacion__ticket', 'cuadrilla').order_by('-fecha_creacion')[:5]
    
    context = {
        'rol': 'administrador',
        
        # Clientes
        'total_clientes_potenciales': total_clientes_potenciales,
        'interes_labels': json.dumps(interes_labels),
        'interes_values': json.dumps(interes_values),
        
        # Contratos
        'total_contratos': total_contratos,
        'contratos_completados': contratos_completados,
        'contratos_proceso': contratos_proceso,
        'contratos_no_completados': contratos_no_completados,
        'contratos_estado_labels': json.dumps(contratos_estado_labels),
        'contratos_estado_values': json.dumps(contratos_estado_values),
        'contratos_estado_colors': json.dumps(contratos_estado_colors),
        
        # Instalaciones
        'total_instalaciones': total_instalaciones,
        'instalaciones_completadas': instalaciones_completadas,
        'instalaciones_pendientes': instalaciones_pendientes,
        'instalaciones_labels': json.dumps(instalaciones_labels),
        'instalaciones_values': json.dumps(instalaciones_values),
        'instalaciones_colors': json.dumps(instalaciones_colors),
        
        # Soportes (CORREGIDO)
        'total_soportes': total_soportes,
        'soportes_pendientes': soportes_pendientes,
        'soportes_proceso': soportes_proceso,
        'soportes_completados': soportes_completados,
        'soportes_tipo_labels': json.dumps(soportes_tipo_labels),
        'soportes_tipo_values': json.dumps(soportes_tipo_values),
        'soportes_tipo_colors': json.dumps(soportes_tipo_colors),
        
        # Asignaciones
        'asignaciones_pendientes': asignaciones_pendientes,
        
        # Últimos
        'ultimos_contratos': ultimos_contratos,
        'ultimas_instalaciones': ultimas_instalaciones,
        'ultimos_soportes': ultimos_soportes,
        
        # Top vendedores
        'top_vendedores': top_vendedores,
    }
    
    return render(request, 'Inicio_De_Sesion/dashboard.html', context)


# ==================== DASHBOARD GENERAL (sin rol específico) ====================
def dashboard_general(request):
    user = request.user
    
    context = {
        'rol': 'general',
        'user': user,
        'mensaje': 'Bienvenido al sistema. Contacta con un administrador para asignarte un rol.',
    }
    
    return render(request, 'dashboard/dashboard.html', context)


# ==================== VISTAS AUXILIARES API ====================
from django.http import JsonResponse

@login_required
def dashboard_datos_api(request):
    """API para obtener datos actualizados del dashboard (para recargas AJAX)"""
    user = request.user
    
    if user.is_superuser or user.groups.filter(name='Administrador').exists():
        hoy = timezone.now().date()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        
        data = {
            'total_contratos': ContratoCliente.objects.count(),
            'contratos_completados': ContratoCliente.objects.filter(estado=ContratoCliente.EstadoContrato.COMPLETADO).count(),
            'instalaciones_completadas': Instalacion.objects.filter(completada=True).count(),
            
            'total_nomina_usd': NominaVendedor.objects.filter(semana_inicio=inicio_semana).aggregate(total=Sum('total_usd'))['total'] or 0,
        }
        
    elif user.groups.filter(name='Vendedor').exists():
        data = {
            'total_contratos': ContratoCliente.objects.filter(creado_por=user).count(),
            'contratos_completados': ContratoCliente.objects.filter(creado_por=user, estado=ContratoCliente.EstadoContrato.COMPLETADO).count(),
        }
        
    elif user.groups.filter(name='Instalador').exists():
        data = {
            'instalaciones_completadas': Instalacion.objects.filter(instaladores=user, completada=True).count(),
            'instalaciones_pendientes': Instalacion.objects.filter(instaladores=user, completada=False).count(),
        }
        
    else:
        data = {'message': 'Sin datos disponibles'}
    
    return JsonResponse(data)


def dashboard_supervisor(request):
    """Dashboard para Supervisores - Solo estadísticas y rendimiento de vendedores"""
    user = request.user
    
    # Fechas para filtros
    hoy = timezone.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    
    # ==================== CONTRATOS ====================
    contratos = ContratoCliente.objects.all()
    
    # Estadísticas generales de contratos
    total_contratos = contratos.count()
    contratos_completados = contratos.filter(estado=ContratoCliente.EstadoContrato.COMPLETADO).count()
    contratos_proceso = contratos.filter(estado=ContratoCliente.EstadoContrato.EN_PROCESO).count()
    contratos_no_completados = contratos.filter(estado=ContratoCliente.EstadoContrato.NO_COMPLETADO).count()
    porcentaje_completado = (contratos_completados / total_contratos * 100) if total_contratos > 0 else 0
    
    # Contratos por mes (últimos 6 meses)
    meses = []
    contratos_por_mes = []
    for i in range(5, -1, -1):
        fecha_inicio = hoy.replace(day=1) - timedelta(days=30*i)
        fecha_fin = (fecha_inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        
        conteo = contratos.filter(fecha_creacion__date__gte=fecha_inicio, fecha_creacion__date__lte=fecha_fin).count()
        meses.append(fecha_inicio.strftime('%b'))
        contratos_por_mes.append(conteo)
    
    # Contratos de esta semana
    contratos_semana = contratos.filter(
        fecha_creacion__date__gte=inicio_semana,
        fecha_creacion__date__lte=fin_semana
    ).count()
    
    # ==================== RENDIMIENTO DE VENDEDORES ====================
    from django.db.models import Count, Q
    
    vendedores = User.objects.filter(
        groups__name='Vendedor',
        is_active=True
    ).annotate(
        total_contratos=Count('contratos_creados'),
        completados=Count('contratos_creados', filter=Q(contratos_creados__estado=ContratoCliente.EstadoContrato.COMPLETADO)),
        en_proceso=Count('contratos_creados', filter=Q(contratos_creados__estado=ContratoCliente.EstadoContrato.EN_PROCESO)),
        no_completados=Count('contratos_creados', filter=Q(contratos_creados__estado=ContratoCliente.EstadoContrato.NO_COMPLETADO))
    ).order_by('-total_contratos')
    
    # Estadísticas de vendedores
    total_vendedores = vendedores.count()
    vendedores_con_contratos = vendedores.filter(total_contratos__gt=0).count()
    vendedores_sin_contratos = total_vendedores - vendedores_con_contratos
    
    # Promedio de contratos por vendedor
    promedio_contratos = sum(v.total_contratos for v in vendedores) / total_vendedores if total_vendedores > 0 else 0
    
    # Top 10 vendedores
    top_vendedores = []
    for v in vendedores[:10]:
        eficiencia = (v.completados / v.total_contratos * 100) if v.total_contratos > 0 else 0
        top_vendedores.append({
            'nombre': v.get_full_name() or v.username,
            'total_contratos': v.total_contratos,
            'completados': v.completados,
            'en_proceso': v.en_proceso,
            'no_completados': v.no_completados,
            'eficiencia': round(eficiencia, 1)
        })
    
    # ==================== PLANES POPULARES ====================
    planes_populares = Plan.objects.filter(activo=True).annotate(
        total_contratos=Count('contratos')
    ).order_by('-total_contratos')[:5]
    
    # ==================== DISTRIBUCIÓN DE ESTADOS (para el gráfico) ====================
    distribucion_estados = [
        {'estado': 'Completados', 'cantidad': contratos_completados, 'color': '#10b981'},
        {'estado': 'En Proceso', 'cantidad': contratos_proceso, 'color': '#f59e0b'},
        {'estado': 'No Completados', 'cantidad': contratos_no_completados, 'color': '#ef4444'},
    ]
    
    # Preparar datos para el gráfico (JSON serializable)
    distribucion_labels = [item['estado'] for item in distribucion_estados]
    distribucion_data = [item['cantidad'] for item in distribucion_estados]
    distribucion_colors = [item['color'] for item in distribucion_estados]
    
    context = {
        'rol': 'supervisor',
        # Estadísticas generales
        'total_contratos': total_contratos,
        'contratos_completados': contratos_completados,
        'contratos_proceso': contratos_proceso,
        'contratos_no_completados': contratos_no_completados,
        'porcentaje_completado': porcentaje_completado,
        'contratos_por_mes': contratos_por_mes,
        'meses': meses,
        'contratos_semana': contratos_semana,
        # Estadísticas de vendedores
        'total_vendedores': total_vendedores,
        'vendedores_con_contratos': vendedores_con_contratos,
        'vendedores_sin_contratos': vendedores_sin_contratos,
        'promedio_contratos': round(promedio_contratos, 1),
        'top_vendedores': top_vendedores,
        # Planes
        'planes_populares': planes_populares,
        # Distribución para gráfico
        'distribucion_labels': distribucion_labels,
        'distribucion_data': distribucion_data,
        'distribucion_colors': distribucion_colors,
    }
    
    return render(request, 'Inicio_De_Sesion/dashboard.html', context)



# ==================== DASHBOARD CALL CENTER ====================
def dashboard_callcenter(request):
    """Dashboard para Call Center - Estadísticas de llamadas y clientes"""
    user = request.user
    
    hoy = timezone.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    
    # ========== ESTADÍSTICAS DE LLAMADAS ==========
    total_llamadas = RegistroLlamada.objects.count()
    llamadas_hoy = RegistroLlamada.objects.filter(fecha_llamada__date=hoy).count()
    llamadas_semana = RegistroLlamada.objects.filter(
        fecha_llamada__date__gte=inicio_semana,
        fecha_llamada__date__lte=fin_semana
    ).count()
    
    # Llamadas por estado
    llamadas_contactados = RegistroLlamada.objects.filter(estado='CONTACTADO').count()
    llamadas_no_responde = RegistroLlamada.objects.filter(estado='NO_RESPONDE').count()
    llamadas_pendientes = RegistroLlamada.objects.filter(estado='PENDIENTE').count()
    
    porcentaje_efectividad = (llamadas_contactados / total_llamadas * 100) if total_llamadas > 0 else 0
    
    # ========== ESTADÍSTICAS DE CLIENTES ==========
    total_contratos = ContratoCliente.objects.count()
    total_potenciales = ClientePotencial.objects.count()
    total_externos = ClienteExterno.objects.count()
    
    # Clientes pendientes por contactar
    from django.db.models import OuterRef, Subquery
    
    ultima_llamada_contrato = RegistroLlamada.objects.filter(
        contrato=OuterRef('pk')
    ).order_by('-fecha_llamada')
    
    contratos_sin_contactar = ContratoCliente.objects.annotate(
        ultimo_estado=Subquery(ultima_llamada_contrato.values('estado')[:1])
    ).filter(
        Q(ultimo_estado__isnull=True) | Q(ultimo_estado='PENDIENTE')
    ).count()
    
    ultima_llamada_potencial = RegistroLlamada.objects.filter(
        cliente_potencial=OuterRef('pk')
    ).order_by('-fecha_llamada')
    
    potenciales_sin_contactar = ClientePotencial.objects.annotate(
        ultimo_estado=Subquery(ultima_llamada_potencial.values('estado')[:1])
    ).filter(
        Q(ultimo_estado__isnull=True) | Q(ultimo_estado='PENDIENTE')
    ).count()
    
    ultima_llamada_externo = RegistroLlamada.objects.filter(
        cliente_externo=OuterRef('pk')
    ).order_by('-fecha_llamada')
    
    externos_sin_contactar = ClienteExterno.objects.annotate(
        ultimo_estado=Subquery(ultima_llamada_externo.values('estado')[:1])
    ).filter(
        Q(ultimo_estado__isnull=True) | Q(ultimo_estado='PENDIENTE')
    ).count()
    
    total_pendientes_contactar = contratos_sin_contactar + potenciales_sin_contactar + externos_sin_contactar
    
    # ========== LLAMADAS POR MES ==========
    meses = []
    llamadas_por_mes = []
    for i in range(5, -1, -1):
        fecha_inicio = hoy.replace(day=1) - timedelta(days=30*i)
        fecha_fin = (fecha_inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        
        conteo = RegistroLlamada.objects.filter(
            fecha_llamada__date__gte=fecha_inicio,
            fecha_llamada__date__lte=fecha_fin
        ).count()
        meses.append(fecha_inicio.strftime('%b'))
        llamadas_por_mes.append(conteo)
    
    # ========== ÚLTIMAS LLAMADAS REALIZADAS (CORREGIDO - SIN ASIGNAR ATRIBUTOS) ==========
    ultimas_llamadas_query = RegistroLlamada.objects.select_related(
        'contrato__cliente_potencial',
        'cliente_potencial',
        'cliente_externo',
        'realizado_por'
    ).order_by('-fecha_llamada')[:10]
    
    # Convertir a lista de diccionarios para evitar asignar atributos
    ultimas_llamadas = []
    for llamada in ultimas_llamadas_query:
        if llamada.contrato:
            nombre_cliente = llamada.contrato.nombre_completo
            telefono_cliente = llamada.contrato.telefono_principal
            tipo_cliente = 'Contrato'
        elif llamada.cliente_potencial:
            nombre_cliente = llamada.cliente_potencial.nombre_completo
            telefono_cliente = llamada.cliente_potencial.telefono
            tipo_cliente = 'Potencial'
        elif llamada.cliente_externo:
            nombre_cliente = llamada.cliente_externo.nombre_completo
            telefono_cliente = llamada.cliente_externo.telefono
            tipo_cliente = 'Externo'
        else:
            nombre_cliente = 'N/A'
            telefono_cliente = 'N/A'
            tipo_cliente = 'N/A'
        
        ultimas_llamadas.append({
            'id': llamada.id,
            'nombre_cliente': nombre_cliente,
            'telefono_cliente': telefono_cliente,
            'tipo_cliente': tipo_cliente,
            'estado': llamada.estado,
            'nota': llamada.nota,
            'fecha_llamada': llamada.fecha_llamada,
            'realizado_por': llamada.realizado_por,
        })
    
    # ========== RENDIMIENTO POR AGENTE (CORREGIDO) ==========
    agentes_query = User.objects.filter(groups__name='Call Center').annotate(
        total_llamadas=Count('llamadas_realizadas'),
        contactados=Count('llamadas_realizadas', filter=Q(llamadas_realizadas__estado='CONTACTADO')),
        no_responde=Count('llamadas_realizadas', filter=Q(llamadas_realizadas__estado='NO_RESPONDE'))
    ).order_by('-total_llamadas')[:5]
    
    # Convertir a lista de diccionarios
    agentes = []
    for agente in agentes_query:
        efectividad = round((agente.contactados / agente.total_llamadas * 100), 1) if agente.total_llamadas > 0 else 0
        agentes.append({
            'id': agente.id,
            'username': agente.username,
            'full_name': agente.get_full_name(),
            'total_llamadas': agente.total_llamadas,
            'contactados': agente.contactados,
            'no_responde': agente.no_responde,
            'efectividad': efectividad,
        })
    
    # ========== CLIENTES CON MAYOR INTENCIÓN ==========
    clientes_interesados = ClientePotencial.objects.filter(
        interesado__in=['SI', 'TAL_VEZ']
    ).exclude(
        id__in=ContratoCliente.objects.values_list('cliente_potencial_id', flat=True)
    ).select_related('creado_por')[:10]
    
    context = {
        'rol': 'callcenter',
        # Estadísticas de llamadas
        'total_llamadas': total_llamadas,
        'llamadas_hoy': llamadas_hoy,
        'llamadas_semana': llamadas_semana,
        'llamadas_contactados': llamadas_contactados,
        'llamadas_no_responde': llamadas_no_responde,
        'llamadas_pendientes': llamadas_pendientes,
        'porcentaje_efectividad': round(porcentaje_efectividad, 1),
        # Estadísticas de clientes
        'total_contratos': total_contratos,
        'total_potenciales': total_potenciales,
        'total_externos': total_externos,
        'total_pendientes_contactar': total_pendientes_contactar,
        # Gráficas
        'meses': json.dumps(meses),
        'llamadas_por_mes': json.dumps(llamadas_por_mes),
        # Últimas llamadas (lista de diccionarios)
        'ultimas_llamadas': ultimas_llamadas,
        # Agentes (lista de diccionarios)
        'agentes': agentes,
        # Clientes con interés
        'clientes_interesados': clientes_interesados,
    }
    
    return render(request, 'Inicio_De_Sesion/dashboard.html', context)