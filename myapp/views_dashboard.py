from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum, Avg, F
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth.models import User, Group
from django.db.models.functions import TruncDate, TruncWeek
from .models import (
    ContratoCliente, ClientePotencial, Cuadrilla, AsignacionContrato,
    Instalacion, Soporte, VentaDirecta, NominaVendedor, Plan
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
    instalaciones_pendientes = total_asignaciones - instalaciones_realizadas.filter(completada=True).count()
    
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
    soportes_recientes = soportes_realizados.order_by('-fecha_creacion')[:5]
    
    # Materiales más usados (promedio)
    materiales = instalaciones_realizadas.filter(completada=True).aggregate(
        avg_conectores=Avg('conectores'),
        avg_rosetas=Avg('rosetas'),
        avg_patch_cord=Avg('patch_cord'),
        avg_metros=Avg(F('inicio_fibra') - F('final_fibra'))
    )
    
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
def dashboard_administrador(request):
    user = request.user
    
    hoy = timezone.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    
    # Estadísticas generales
    total_clientes_potenciales = ClientePotencial.objects.count()
    total_contratos = ContratoCliente.objects.count()
    total_ventas_directas = VentaDirecta.objects.count()
    
    # Contratos por estado
    contratos_proceso = ContratoCliente.objects.filter(estado=ContratoCliente.EstadoContrato.EN_PROCESO).count()
    contratos_completados = ContratoCliente.objects.filter(estado=ContratoCliente.EstadoContrato.COMPLETADO).count()
    contratos_no_completados = ContratoCliente.objects.filter(estado=ContratoCliente.EstadoContrato.NO_COMPLETADO).count()
    
    # Instalaciones
    total_instalaciones = Instalacion.objects.count()
    instalaciones_completadas = Instalacion.objects.filter(completada=True).count()
    instalaciones_pendientes = total_instalaciones - instalaciones_completadas
    
    # Soportes por tipo
    soportes_mudanza = Soporte.objects.filter(tipo=Soporte.TipoSoporte.MUDANZA).count()
    soportes_retiro = Soporte.objects.filter(tipo=Soporte.TipoSoporte.RETIRO).count()
    soportes_recableado = Soporte.objects.filter(tipo=Soporte.TipoSoporte.RECABLEADO).count()
    soportes_pendientes = Soporte.objects.filter(estado=Soporte.EstadoSoporte.PENDIENTE).count()
    
    # Gráfico de contratos por mes (últimos 6 meses)
    meses = []
    contratos_por_mes = []
    ventas_por_mes = []
    for i in range(5, -1, -1):
        fecha_inicio = hoy.replace(day=1) - timedelta(days=30*i)
        fecha_fin = (fecha_inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        
        contratos_mes = ContratoCliente.objects.filter(
            fecha_creacion__date__gte=fecha_inicio,
            fecha_creacion__date__lte=fecha_fin
        ).count()
        
        ventas_mes = VentaDirecta.objects.filter(
            fecha_creacion__date__gte=fecha_inicio,
            fecha_creacion__date__lte=fecha_fin
        ).count()
        
        meses.append(fecha_inicio.strftime('%b %Y'))
        contratos_por_mes.append(contratos_mes)
        ventas_por_mes.append(ventas_mes)
    
    # Ranking de vendedores
    ranking_vendedores = User.objects.filter(groups__name='Vendedor').annotate(
        total_contratos=Count('contratos_creados', filter=Q(contratos_creados__estado=ContratoCliente.EstadoContrato.COMPLETADO))
    ).order_by('-total_contratos')[:10]
    
    # Ranking de cuadrillas
    ranking_cuadrillas = Cuadrilla.objects.annotate(
        total_instalaciones=Count('asignaciones__instalacion', filter=Q(asignaciones__instalacion__completada=True))
    ).order_by('-total_instalaciones')[:5]
    
    # Últimos contratos
    ultimos_contratos = ContratoCliente.objects.select_related(
        'cliente_potencial', 'plan_contratado', 'creado_por'
    ).order_by('-fecha_creacion')[:10]
    
    # Planes más vendidos
    planes_populares = Plan.objects.annotate(
        total_contratos=Count('contratos'),
        total_ventas_directas=Count('ventas_directas')
    ).order_by('-total_contratos')[:5]
    
    # Asignaciones pendientes
    asignaciones_pendientes = AsignacionContrato.objects.filter(
        activo=True
    ).exclude(
        id__in=Instalacion.objects.values_list('asignacion_id', flat=True)
    ).select_related('contrato__cliente_potencial', 'venta_directa', 'cuadrilla').count()
    
    # Nómina de la semana
    nominas_semana = NominaVendedor.objects.filter(
        semana_inicio=inicio_semana
    ).select_related('vendedor').order_by('-total_usd')
    
    total_nomina_usd = nominas_semana.aggregate(total=Sum('total_usd'))['total'] or 0
    
    # Soporte por estado
    soportes_estado = {
        'pendientes': Soporte.objects.filter(estado=Soporte.EstadoSoporte.PENDIENTE).count(),
        'proceso': Soporte.objects.filter(estado=Soporte.EstadoSoporte.EN_PROCESO).count(),
        'completados': Soporte.objects.filter(estado=Soporte.EstadoSoporte.COMPLETADO).count(),
    }
    
    context = {
        'rol': 'administrador',
        'total_clientes_potenciales': total_clientes_potenciales,
        'total_contratos': total_contratos,
        'total_ventas_directas': total_ventas_directas,
        'contratos_proceso': contratos_proceso,
        'contratos_completados': contratos_completados,
        'contratos_no_completados': contratos_no_completados,
        'total_instalaciones': total_instalaciones,
        'instalaciones_completadas': instalaciones_completadas,
        'instalaciones_pendientes': instalaciones_pendientes,
        'porcentaje_instalaciones': (instalaciones_completadas / total_instalaciones * 100) if total_instalaciones > 0 else 0,
        'soportes_mudanza': soportes_mudanza,
        'soportes_retiro': soportes_retiro,
        'soportes_recableado': soportes_recableado,
        'soportes_pendientes': soportes_pendientes,
        'meses': meses,
        'contratos_por_mes': contratos_por_mes,
        'ventas_por_mes': ventas_por_mes,
        'ranking_vendedores': ranking_vendedores,
        'ranking_cuadrillas': ranking_cuadrillas,
        'ultimos_contratos': ultimos_contratos,
        'planes_populares': planes_populares,
        'asignaciones_pendientes': asignaciones_pendientes,
        'nominas_semana': nominas_semana,
        'total_nomina_usd': total_nomina_usd,
        'soportes_estado': soportes_estado,
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
            'soportes_pendientes': Soporte.objects.filter(estado=Soporte.EstadoSoporte.PENDIENTE).count(),
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