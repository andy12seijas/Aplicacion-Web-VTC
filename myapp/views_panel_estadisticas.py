# views.py - Agregar esta función
from django.contrib.auth.decorators import login_required
import json
from pyexpat.errors import messages
from django.db.models import Count, Q, Sum, Avg
from django.shortcuts import redirect, render
from django.utils import timezone
from datetime import timedelta, datetime
from calendar import monthrange
from django.http import JsonResponse
from django.template.loader import render_to_string
from myapp.models import *
from datetime import datetime, timedelta
# views_panel_estadisticas.py
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
import json
from myapp.models import (
    ClientePotencial, ContratoCliente, VentaDirecta, 
    Instalacion, AsignacionContrato, User, Cuadrilla
)

@login_required
def panel_estadisticas(request):
    """Panel de estadísticas para administrador con pestañas de vendedores e instaladores"""
    
    # Verificar permisos (solo administradores)
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_supervisor = request.user.groups.filter(name='Supervisor').exists()
    
    # El panel es accesible para Admin y Supervisor
    if not (es_admin or es_supervisor):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # ========== DEFINIR RANGO DE FECHAS POR DEFECTO ==========
    hoy = timezone.now().date()
    
    if hoy.day >= 3:
        fecha_inicio = datetime(hoy.year, hoy.month, 3).date()
        fecha_fin = fecha_inicio + timedelta(days=30)
        if fecha_fin.day > 2:
            fecha_fin = datetime(fecha_fin.year, fecha_fin.month, 2).date()
    else:
        mes_anterior = hoy.month - 1 if hoy.month > 1 else 12
        año_anterior = hoy.year if hoy.month > 1 else hoy.year - 1
        fecha_inicio = datetime(año_anterior, mes_anterior, 3).date()
        fecha_fin = datetime(hoy.year, hoy.month, 2).date()
    
    # Obtener fechas del filtro
    fecha_inicio_str = request.GET.get('fecha_inicio', fecha_inicio.strftime('%Y-%m-%d'))
    fecha_fin_str = request.GET.get('fecha_fin', fecha_fin.strftime('%Y-%m-%d'))
    
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except:
        pass
    
    # Filtros adicionales
    filtro_vendedor = request.GET.get('vendedor', '')
    filtro_cuadrilla = request.GET.get('cuadrilla', '')
    
    # Obtener pestaña activa
    tab_activa = request.GET.get('tab', 'vendedores')
    
    # ========== CONSULTAS BASE ==========
    
    # Contratos en el período
    contratos = ContratoCliente.objects.filter(
        fecha_creacion__date__gte=fecha_inicio,
        fecha_creacion__date__lte=fecha_fin
    )
    
    # Ventas directas en el período
    ventas_directas = VentaDirecta.objects.filter(
        fecha_creacion__date__gte=fecha_inicio,
        fecha_creacion__date__lte=fecha_fin
    )
    
    # Clientes en el período
    clientes = ClientePotencial.objects.filter(
        fecha_creacion__date__gte=fecha_inicio,
        fecha_creacion__date__lte=fecha_fin
    )
    
    # Instalaciones
    instalaciones = Instalacion.objects.filter(
        fecha_creacion__date__gte=fecha_inicio,
        fecha_creacion__date__lte=fecha_fin
    )
    
    instalaciones_completadas = instalaciones.filter(completada=True)
    instalaciones_pendientes = instalaciones.filter(completada=False)
    
    # Aplicar filtro de vendedor
    clientes_filtrados = clientes
    contratos_filtrados = contratos
    ventas_directas_filtradas = ventas_directas
    
    if filtro_vendedor:
        clientes_filtrados = clientes.filter(creado_por_id=filtro_vendedor)
        contratos_filtrados = contratos.filter(creado_por_id=filtro_vendedor)
        ventas_directas_filtradas = ventas_directas.filter(creado_por_id=filtro_vendedor)
    
    # Aplicar filtro de cuadrilla
    instalaciones_filtradas = instalaciones
    instalaciones_completadas_filtradas = instalaciones_completadas
    instalaciones_pendientes_filtradas = instalaciones_pendientes
    
    if filtro_cuadrilla:
        asignaciones = AsignacionContrato.objects.filter(cuadrilla_id=filtro_cuadrilla)
        instalaciones_filtradas = instalaciones.filter(asignacion__in=asignaciones)
        instalaciones_completadas_filtradas = instalaciones_completadas.filter(asignacion__in=asignaciones)
        instalaciones_pendientes_filtradas = instalaciones_pendientes.filter(asignacion__in=asignaciones)
    
    # ========== DATOS PARA VENDEDORES ==========
    
    # Obtener el vendedor seleccionado (si existe)
    vendedor_seleccionado = None
    if filtro_vendedor:
        try:
            vendedor_seleccionado = User.objects.get(id=filtro_vendedor)
        except:
            pass
    
    # Estadísticas generales vendedores
    total_clientes_vendedores = clientes_filtrados.count()
    total_contratos = contratos_filtrados.count()
    total_ventas_directas = ventas_directas_filtradas.count()
    
    clientes_con_contrato_vendedores = ClientePotencial.objects.filter(
        id__in=contratos_filtrados.values_list('cliente_potencial_id', flat=True)
    ).count()
    
    tasa_conversion_vendedores = round((clientes_con_contrato_vendedores / total_clientes_vendedores * 100) if total_clientes_vendedores > 0 else 0, 1)
    
    # Evolución de contratos por día
    fechas = []
    ventas_diarias = []
    instalaciones_diarias = []
    conversion_diaria = []
    delta_days = (fecha_fin - fecha_inicio).days + 1
    
    for i in range(delta_days):
        fecha = fecha_inicio + timedelta(days=i)
        fechas.append(fecha.strftime('%d/%m'))
        ventas_dia = contratos_filtrados.filter(fecha_creacion__date=fecha).count()
        ventas_diarias.append(ventas_dia)
        instalaciones_dia = instalaciones_filtradas.filter(fecha_creacion__date=fecha).count()
        instalaciones_diarias.append(instalaciones_dia)
        clientes_dia = clientes_filtrados.filter(fecha_creacion__date=fecha).count()
        conversion = round((ventas_dia / clientes_dia * 100) if clientes_dia > 0 else 0, 1)
        conversion_diaria.append(conversion)
    
    # Distribución de ventas
    tipos_venta = ['Contratos Vendedor', 'Ventas Directas']
    valores_tipos = [total_contratos, total_ventas_directas]
    colores_tipos = ['#ff6b00', '#2196f3']
    
    # Top 5 Vendedores (con datos completos para la lista)
    top_vendedores = User.objects.filter(
        contratos_creados__fecha_creacion__date__gte=fecha_inicio,
        contratos_creados__fecha_creacion__date__lte=fecha_fin
    ).annotate(
        total_contratos=Count('contratos_creados')
    ).order_by('-total_contratos')[:5]
    
    top_vendedores_nombres = []
    top_vendedores_valores = []
    top_vendedores_data = []
    
    for v in top_vendedores:
        nombre = v.get_full_name() or v.username
        top_vendedores_nombres.append(nombre)
        top_vendedores_valores.append(v.total_contratos)
        
        # Obtener clientes del vendedor en el período
        clientes_v = ClientePotencial.objects.filter(
            creado_por=v,
            fecha_creacion__date__gte=fecha_inicio,
            fecha_creacion__date__lte=fecha_fin
        ).count()
        
        # Obtener contratos completados del vendedor
        contratos_completados = ContratoCliente.objects.filter(
            creado_por=v,
            estado='COMPLETADO',
            fecha_creacion__date__gte=fecha_inicio,
            fecha_creacion__date__lte=fecha_fin
        ).count()
        
        # Calcular porcentaje de completados
        porcentaje = round((contratos_completados / v.total_contratos * 100) if v.total_contratos > 0 else 0, 1)
        
        top_vendedores_data.append({
            'nombre': nombre,
            'clientes': clientes_v,
            'contratos': v.total_contratos,
            'completados': contratos_completados,
            'porcentaje': porcentaje
        })
    
    # Tasa de conversión por vendedor
    conversion_vendedores = []
    vendedores_con_version = User.objects.filter(
        Q(clientes_potenciales_creados__fecha_creacion__date__gte=fecha_inicio) |
        Q(contratos_creados__fecha_creacion__date__gte=fecha_inicio)
    ).distinct()
    
    # Si hay un filtro de vendedor, mostrar solo ese
    if filtro_vendedor and vendedor_seleccionado:
        vendedores_para_conversion = [vendedor_seleccionado]
    else:
        vendedores_para_conversion = vendedores_con_version[:10]
    
    for v in vendedores_para_conversion:
        clientes_v = ClientePotencial.objects.filter(
            creado_por=v,
            fecha_creacion__date__gte=fecha_inicio,
            fecha_creacion__date__lte=fecha_fin
        ).count()
        contratos_v = ContratoCliente.objects.filter(
            creado_por=v,
            fecha_creacion__date__gte=fecha_inicio,
            fecha_creacion__date__lte=fecha_fin
        ).count()
        conversion = round((contratos_v / clientes_v * 100) if clientes_v > 0 else 0, 1)
        if clientes_v > 0 or contratos_v > 0:
            conversion_vendedores.append({
                'nombre': v.get_full_name() or v.username,
                'conversion': conversion
            })
    
    conversion_vendedores = sorted(conversion_vendedores, key=lambda x: x['conversion'], reverse=True)
    conversion_vendedores_nombres = [c['nombre'] for c in conversion_vendedores]
    conversion_vendedores_valores = [c['conversion'] for c in conversion_vendedores]
    
    # Estado de contratos
    estados_contratos = ['En Proceso', 'Completado', 'No Completado']
    estados_valores = [
        contratos_filtrados.filter(estado='EN_PROCESO').count(),
        contratos_filtrados.filter(estado='COMPLETADO').count(),
        contratos_filtrados.filter(estado='NO_COMPLETADO').count()
    ]
    estados_colores = ['#ff9800', '#4caf50', '#f44336']
    
    # ========== DATOS PARA INSTALADORES ==========
    
    # Obtener la cuadrilla seleccionada (si existe)
    cuadrilla_seleccionada = None
    if filtro_cuadrilla:
        try:
            cuadrilla_seleccionada = Cuadrilla.objects.get(id=filtro_cuadrilla)
        except:
            pass
    
    # Estadísticas generales instaladores
    total_instalaciones_completadas = instalaciones_completadas_filtradas.count()
    total_instalaciones_pendientes = instalaciones_pendientes_filtradas.count()
    total_instalaciones_general = instalaciones_filtradas.count()
    
    eficiencia_instalacion = round((total_instalaciones_completadas / total_instalaciones_general * 100) if total_instalaciones_general > 0 else 0, 1)
    
    total_cuadrillas_activas = Cuadrilla.objects.filter(activo=True).count()
    total_vendedores = User.objects.filter(groups__name='Vendedor').distinct().count()
    total_cuadrillas = Cuadrilla.objects.filter(activo=True).count()
    
    # Instalaciones por día (completadas y pendientes)
    instalaciones_completadas_diarias = []
    instalaciones_pendientes_diarias = []
    
    for i in range(delta_days):
        fecha = fecha_inicio + timedelta(days=i)
        completadas_dia = instalaciones_completadas_filtradas.filter(fecha_instalacion__date=fecha).count()
        pendientes_dia = instalaciones_pendientes_filtradas.filter(fecha_creacion__date=fecha).count()
        instalaciones_completadas_diarias.append(completadas_dia)
        instalaciones_pendientes_diarias.append(pendientes_dia)
    
    # Rendimiento por cuadrilla
    if filtro_cuadrilla and cuadrilla_seleccionada:
        cuadrillas_rendimiento = [cuadrilla_seleccionada]
        cuadrillas_nombres = [cuadrilla_seleccionada.nombre]
        cuadrillas_completadas = [Instalacion.objects.filter(
            asignacion__cuadrilla=cuadrilla_seleccionada,
            completada=True,
            fecha_instalacion__date__gte=fecha_inicio,
            fecha_instalacion__date__lte=fecha_fin
        ).count()]
    else:
        cuadrillas_rendimiento = Cuadrilla.objects.filter(activo=True).annotate(
            instalaciones_completadas=Count('asignaciones__instalacion', filter=Q(
                asignaciones__instalacion__completada=True,
                asignaciones__instalacion__fecha_instalacion__date__gte=fecha_inicio,
                asignaciones__instalacion__fecha_instalacion__date__lte=fecha_fin
            ))
        ).order_by('-instalaciones_completadas')[:5]
        
        cuadrillas_nombres = []
        cuadrillas_completadas = []
        for c in cuadrillas_rendimiento:
            cuadrillas_nombres.append(c.nombre)
            cuadrillas_completadas.append(c.instalaciones_completadas)
    
    # ========== DATOS PARA RANKING DE CUADRILLAS ==========
    cuadrillas_rendimiento_data = []
    
    # Obtener todas las cuadrillas activas para el ranking
    if filtro_cuadrilla and cuadrilla_seleccionada:
        cuadrillas_para_ranking = [cuadrilla_seleccionada]
    else:
        cuadrillas_para_ranking = Cuadrilla.objects.filter(activo=True).order_by('nombre')
    
    for c in cuadrillas_para_ranking:
        # Obtener instalaciones completadas de la cuadrilla en el período
        completadas = Instalacion.objects.filter(
            asignacion__cuadrilla=c,
            completada=True,
            fecha_instalacion__date__gte=fecha_inicio,
            fecha_instalacion__date__lte=fecha_fin
        ).count()
        
        # Obtener instalaciones pendientes
        pendientes = Instalacion.objects.filter(
            asignacion__cuadrilla=c,
            completada=False,
            fecha_creacion__date__gte=fecha_inicio,
            fecha_creacion__date__lte=fecha_fin
        ).count()
        
        # Solo agregar cuadrillas que tengan al menos una instalación
        if completadas > 0 or pendientes > 0:
            # Calcular eficiencia
            total = completadas + pendientes
            eficiencia = round((completadas / total * 100) if total > 0 else 0, 1)
            
            # Obtener nombres de los instaladores
            instaladores = []
            for inst in c.instaladores.all():
                nombre = inst.usuario.get_full_name() or inst.usuario.username
                instaladores.append(nombre)
            
            cuadrillas_rendimiento_data.append({
                'id': c.id,
                'nombre': c.nombre,
                'completadas': completadas,
                'pendientes': pendientes,
                'eficiencia': eficiencia,
                'instaladores': instaladores
            })
    
    # Ordenar por eficiencia (mayor a menor) y luego por completadas
    cuadrillas_rendimiento_data.sort(key=lambda x: (-x['eficiencia'], -x['completadas']))
    
    # Limitar a top 5
    cuadrillas_rendimiento_data = cuadrillas_rendimiento_data[:5]
    
    # Tasa de completación diaria
    tasa_completacion_diaria = []
    for i in range(delta_days):
        fecha = fecha_inicio + timedelta(days=i)
        total_dia = instalaciones_filtradas.filter(fecha_creacion__date=fecha).count()
        completadas_dia = instalaciones_completadas_filtradas.filter(fecha_instalacion__date=fecha).count()
        tasa = round((completadas_dia / total_dia * 100) if total_dia > 0 else 0, 1)
        tasa_completacion_diaria.append(tasa)
    
    # ========== OBTENER LISTAS PARA FILTROS ==========
    vendedores = User.objects.filter(
        Q(groups__name='Vendedor') | Q(is_superuser=True)
    ).distinct().order_by('first_name', 'username')
    
    cuadrillas = Cuadrilla.objects.filter(activo=True).order_by('nombre')
    
    # ========== CONTEXTO ==========
    context = {
        # Fechas
        'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d'),
        'fecha_fin': fecha_fin.strftime('%Y-%m-%d'),
        'fecha_inicio_display': fecha_inicio.strftime('%d/%m/%Y'),
        'fecha_fin_display': fecha_fin.strftime('%d/%m/%Y'),
        
        # Datos para vendedores
        'total_clientes_vendedores': total_clientes_vendedores,
        'total_contratos': total_contratos,
        'total_ventas_directas': total_ventas_directas,
        'tasa_conversion_vendedores': tasa_conversion_vendedores,
        'clientes_con_contrato_vendedores': clientes_con_contrato_vendedores,
        
        # Datos para instaladores
        'total_instalaciones_completadas': total_instalaciones_completadas,
        'total_instalaciones_pendientes': total_instalaciones_pendientes,
        'eficiencia_instalacion': eficiencia_instalacion,
        'total_cuadrillas_activas': total_cuadrillas_activas,
        'total_vendedores': total_vendedores,
        'total_cuadrillas': total_cuadrillas,
        
        # Gráficas comunes
        'fechas_json': json.dumps(fechas),
        'ventas_diarias_json': json.dumps(ventas_diarias),
        'instalaciones_diarias_json': json.dumps(instalaciones_diarias),
        'conversion_diaria_json': json.dumps(conversion_diaria),
        
        # Gráficas vendedores
        'tipos_venta_json': json.dumps(tipos_venta),
        'valores_tipos_json': json.dumps(valores_tipos),
        'colores_tipos_json': json.dumps(colores_tipos),
        
        'top_vendedores_nombres_json': json.dumps(top_vendedores_nombres),
        'top_vendedores_valores_json': json.dumps(top_vendedores_valores),
        'top_vendedores_data': top_vendedores_data,
        
        'conversion_vendedores_nombres_json': json.dumps(conversion_vendedores_nombres),
        'conversion_vendedores_valores_json': json.dumps(conversion_vendedores_valores),
        
        'estados_contratos_json': json.dumps(estados_contratos),
        'estados_valores_json': json.dumps(estados_valores),
        'estados_colores_json': json.dumps(estados_colores),
        
        # Gráficas instaladores
        'instalaciones_completadas_diarias_json': json.dumps(instalaciones_completadas_diarias),
        'instalaciones_pendientes_diarias_json': json.dumps(instalaciones_pendientes_diarias),
        
        'cuadrillas_nombres_json': json.dumps(cuadrillas_nombres),
        'cuadrillas_completadas_json': json.dumps(cuadrillas_completadas),
        
        'tasa_completacion_diaria_json': json.dumps(tasa_completacion_diaria),
        
        # Ranking de cuadrillas
        'cuadrillas_rendimiento_data': cuadrillas_rendimiento_data,
        
        # Filtros
        'vendedores': vendedores,
        'cuadrillas': cuadrillas,
        'filtro_vendedor': filtro_vendedor,
        'filtro_cuadrilla': filtro_cuadrilla,
        'tab_activa': tab_activa,
        'vendedor_seleccionado': vendedor_seleccionado,
        'cuadrilla_seleccionada': cuadrilla_seleccionada,
        'es_supervisor': es_supervisor,
    }
    
    return render(request, 'Admin/panel_estadistica.html', context)