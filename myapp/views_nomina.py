# ==================== FUNCIONES AUXILIARES PARA NÓMINA ====================
# Colocar estas funciones en views.py

from datetime import date, datetime, timedelta
from django.db import transaction
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.contrib import messages
from myapp.models import ContratoCliente, NominaVendedor, TasaCambio
from django.contrib.auth.models import User, Group 

def obtener_semana_por_fecha(fecha):
    """
    Obtiene el viernes de inicio de semana y viernes de fin para una fecha dada.
    La semana va de viernes a viernes.
    
    Args:
        fecha: Fecha (datetime.date)
    
    Returns:
        tuple: (viernes_inicio, viernes_fin)
    """
    # Encontrar el viernes de la semana (día 4 = viernes, 0=lunes, 4=viernes)
    dias_hasta_viernes = 4 - fecha.weekday()
    if dias_hasta_viernes < 0:
        dias_hasta_viernes += 7
    
    viernes_inicio = fecha - timedelta(days=dias_hasta_viernes)
    viernes_fin = viernes_inicio + timedelta(days=7)
    
    return viernes_inicio, viernes_fin


def actualizar_nomina_por_fecha(vendedor_id, fecha_completado):
    """
    Actualiza la nómina del vendedor para la semana de la fecha de completado.
    
    Args:
        vendedor_id: ID del vendedor (User)
        fecha_completado: Fecha en que se completó el contrato
    
    Returns:
        NominaVendedor: El objeto de nómina actualizado
    """
    with transaction.atomic():
        # Obtener la semana de la fecha de completado
        inicio_semana, fin_semana = obtener_semana_por_fecha(fecha_completado)
        
        # Contar todos los contratos completados del vendedor en esa semana
        total_contratos = ContratoCliente.objects.filter(
            creado_por_id=vendedor_id,
            estado=ContratoCliente.EstadoContrato.COMPLETADO,
            fecha_actualizacion__date__gte=inicio_semana,
            fecha_actualizacion__date__lt=fin_semana
        ).count()
        
        # Obtener o crear la nómina de esa semana
        nomina, created = NominaVendedor.objects.get_or_create(
            vendedor_id=vendedor_id,
            semana_inicio=inicio_semana,
            defaults={
                'semana_fin': fin_semana,
                'total_contratos': total_contratos
            }
        )
        
        if not created:
            nomina.total_contratos = total_contratos
            nomina.save()
        
        return nomina


def recalcular_todas_nominas():
    """
    Recalcula todas las nóminas de todos los vendedores para todas las semanas.
    Útil para cuando se necesita recalcular todo desde cero.
    
    Returns:
        list: Lista de nóminas actualizadas
    """
    # Eliminar todas las nóminas existentes (opcional, para recalcular desde cero)
    NominaVendedor.objects.all().delete()
    
    # Obtener todos los contratos completados
    contratos_completados = ContratoCliente.objects.filter(
        estado=ContratoCliente.EstadoContrato.COMPLETADO
    ).select_related('creado_por')
    
    # Diccionario para agrupar por vendedor y semana
    grupos = {}
    
    for contrato in contratos_completados:
        if not contrato.creado_por:
            continue
            
        vendedor_id = contrato.creado_por.id
        fecha_completado = contrato.fecha_actualizacion.date()
        inicio_semana, fin_semana = obtener_semana_por_fecha(fecha_completado)
        
        clave = (vendedor_id, inicio_semana)
        
        if clave not in grupos:
            grupos[clave] = {
                'vendedor_id': vendedor_id,
                'semana_inicio': inicio_semana,
                'semana_fin': fin_semana,
                'contratos': []
            }
        
        grupos[clave]['contratos'].append(contrato)
    
    # Crear las nóminas
    resultados = []
    for clave, data in grupos.items():
        total_contratos = len(data['contratos'])
        
        nomina, created = NominaVendedor.objects.update_or_create(
            vendedor_id=data['vendedor_id'],
            semana_inicio=data['semana_inicio'],
            defaults={
                'semana_fin': data['semana_fin'],
                'total_contratos': total_contratos
            }
        )
        resultados.append(nomina)
    
    return resultados


def obtener_resumen_nomina(fecha_inicio=None, fecha_fin=None, vendedor_id=None):
    """
    Obtiene el resumen de nómina con filtros opcionales.
    
    Args:
        fecha_inicio: Fecha de inicio del período (opcional)
        fecha_fin: Fecha de fin del período (opcional)
        vendedor_id: ID del vendedor (opcional)
    
    Returns:
        QuerySet: Lista de nóminas filtradas
    """
    queryset = NominaVendedor.objects.select_related('vendedor').order_by('-semana_inicio')
    
    if fecha_inicio:
        queryset = queryset.filter(semana_inicio__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(semana_fin__lte=fecha_fin)
    if vendedor_id:
        queryset = queryset.filter(vendedor_id=vendedor_id)
    
    return queryset


def obtener_resumen_por_vendedor(fecha_inicio=None, fecha_fin=None):
    """
    Obtiene el resumen agrupado por vendedor para la tabla principal.
    
    Args:
        fecha_inicio: Fecha de inicio del período (opcional)
        fecha_fin: Fecha de fin del período (opcional)
    
    Returns:
        list: Lista de diccionarios con el resumen por vendedor
    """
    queryset = NominaVendedor.objects.select_related('vendedor')
    
    if fecha_inicio:
        queryset = queryset.filter(semana_inicio__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(semana_fin__lte=fecha_fin)
    
    # Agrupar por vendedor
    resumen = queryset.values(
        'vendedor__id',
        'vendedor__first_name',
        'vendedor__last_name',
        'vendedor__username'
    ).annotate(
        total_contratos=Sum('total_contratos'),
        total_comision=Sum('comision_total_usd'),
        total_bono=Sum('bono_usd'),
        total_usd=Sum('total_usd')
    ).order_by('-total_contratos')
    
    # Agregar el total en bolívares (calculado con la tasa activa)
    tasa = TasaCambio.get_tasa_activa()
    for item in resumen:
        item['total_bs'] = item['total_usd'] * tasa
    
    return resumen


# ==================== VISTAS PARA NÓMINA ====================

def resumen_nomina(request):
    """
    Vista para mostrar el resumen de nómina en formato calendario (viernes a jueves)
    Con filtro por mes (Enero a Diciembre del año actual) y navegación por semanas
    """
    # Verificar permisos
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    from datetime import date, datetime, timedelta
    import calendar
    from django.db.models import Q
    
    # Diccionario para nombres de meses en español
    meses_espanol = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    
    # Días de la semana en español
    dias_espanol = {
        'Mon': 'Lun', 'Tue': 'Mar', 'Wed': 'Mié', 'Thu': 'Jue',
        'Fri': 'Vie', 'Sat': 'Sáb', 'Sun': 'Dom'
    }
    
    # Obtener el año actual
    año_actual = date.today().year
    
    # Crear lista de meses disponibles (Enero a Diciembre del año actual)
    meses_disponibles = []
    for mes in range(1, 13):
        meses_disponibles.append({
            'nombre': f"{meses_espanol[mes]} {año_actual}",
            'valor': f"{año_actual}_{mes}"
        })
    
    # Obtener parámetros
    mes_seleccionado = request.GET.get('mes', '')
    semana_idx = int(request.GET.get('semana_idx', 0))
    
    # Determinar el mes a mostrar
    if mes_seleccionado:
        año, mes = map(int, mes_seleccionado.split('_'))
    else:
        # Por defecto, mes actual
        año = año_actual
        mes = date.today().month
        mes_seleccionado = f"{año}_{mes}"
    
    # Obtener las 4 semanas del mes (viernes a jueves)
    def obtener_semanas_del_mes(año, mes):
        """Retorna las 4 semanas del mes (viernes a jueves)"""
        # Primer día del mes
        primer_dia = date(año, mes, 1)
        # Encontrar el primer viernes del mes
        dias_hasta_viernes = 4 - primer_dia.weekday()
        if dias_hasta_viernes < 0:
            dias_hasta_viernes += 7
        primer_viernes = primer_dia + timedelta(days=dias_hasta_viernes)
        
        semanas = []
        for i in range(4):
            inicio = primer_viernes + timedelta(days=i*7)
            fin = inicio + timedelta(days=6)
            semanas.append({
                'inicio': inicio,
                'fin': fin,
                'numero': i + 1
            })
        return semanas
    
    semanas_mes = obtener_semanas_del_mes(año, mes)
    
    # Asegurar que semana_idx esté dentro del rango
    if semana_idx < 0:
        semana_idx = 0
    if semana_idx >= len(semanas_mes):
        semana_idx = len(semanas_mes) - 1
    
    semana_actual = semanas_mes[semana_idx]
    semana_inicio = semana_actual['inicio']
    semana_fin = semana_actual['fin']
    numero_semana = semana_actual['numero']
    
    # Calcular los 7 días de la semana (viernes a jueves)
    dias_semana = []
    for i in range(7):
        fecha = semana_inicio + timedelta(days=i)
        nombre_dia = dias_espanol.get(fecha.strftime('%a'), fecha.strftime('%a'))
        dias_semana.append({
            'dia': fecha.day,
            'nombre': nombre_dia,
            'fecha': fecha
        })
    
    # Obtener todos los vendedores con contratos en esta semana
    vendedores = User.objects.filter(
        contratos_creados__estado=ContratoCliente.EstadoContrato.COMPLETADO,
        contratos_creados__fecha_actualizacion__date__gte=semana_inicio,
        contratos_creados__fecha_actualizacion__date__lte=semana_fin
    ).distinct().order_by('first_name', 'username')
    
    # Si no hay vendedores con contratos, mostrar todos los que tienen perfil
    if not vendedores:
        vendedores = User.objects.filter(perfil__isnull=False).order_by('first_name', 'username')
    
    # Crear estructura de datos
    calendario = []
    totales_por_dia = [0] * 7
    total_contratos_general = 0
    total_comision_general = 0
    total_bono_general = 0
    total_usd_general = 0
    
    for vendedor in vendedores:
        dias_contratos = [0] * 7
        total_contratos_vendedor = 0
        
        contratos = ContratoCliente.objects.filter(
            creado_por=vendedor,
            estado=ContratoCliente.EstadoContrato.COMPLETADO,
            fecha_actualizacion__date__gte=semana_inicio,
            fecha_actualizacion__date__lte=semana_fin
        )
        
        for contrato in contratos:
            fecha_comp = contrato.fecha_actualizacion.date()
            dias_diferencia = (fecha_comp - semana_inicio).days
            if 0 <= dias_diferencia < 7:
                dias_contratos[dias_diferencia] += 1
                total_contratos_vendedor += 1
                totales_por_dia[dias_diferencia] += 1
        
        # Calcular comisión y bono
        if total_contratos_vendedor >= 1 and total_contratos_vendedor <= 5:
            comision_por_contrato = 8
            bono = 20
        elif total_contratos_vendedor >= 6 and total_contratos_vendedor <= 10:
            comision_por_contrato = 10
            bono = 40
        elif total_contratos_vendedor >= 11:
            comision_por_contrato = 10
            bono = 60
        else:
            comision_por_contrato = 0
            bono = 0
        
        comision_total = total_contratos_vendedor * comision_por_contrato
        total_usd = comision_total + bono
        tasa = TasaCambio.get_tasa_activa()
        total_bs = total_usd * tasa
        
        total_contratos_general += total_contratos_vendedor
        total_comision_general += comision_total
        total_bono_general += bono
        total_usd_general += total_usd
        
        calendario.append({
            'nombre': vendedor.get_full_name() or vendedor.username,
            'username': vendedor.username,
            'dias': dias_contratos,
            'total_contratos': total_contratos_vendedor,
            'comision': comision_total,
            'bono': bono,
            'total_usd': total_usd,
            'total_bs': total_bs
        })
    
    # Ordenar por total de contratos (los que tienen más contratos primero)
    calendario.sort(key=lambda x: x['total_contratos'], reverse=True)
    
    total_bs_general = total_usd_general * TasaCambio.get_tasa_activa()
    
    # Preparar totales por día para el template
    totales_por_dia_lista = [{'total': t} for t in totales_por_dia]
    
    context = {
        'calendario': calendario,
        'dias_semana': dias_semana,
        'semana_inicio': semana_inicio,
        'semana_fin': semana_fin,
        'numero_semana': numero_semana,
        'totales_por_dia': totales_por_dia_lista,
        'total_contratos': total_contratos_general,
        'total_comision': total_comision_general,
        'total_bono': total_bono_general,
        'total_usd': total_usd_general,
        'total_bs': total_bs_general,
        'tasa_activa': TasaCambio.get_tasa_activa(),
        'meses_disponibles': meses_disponibles,
        'mes_seleccionado': mes_seleccionado,
        'mes_nombre': meses_espanol[mes],
        'semana_anterior_disabled': semana_idx == 0,
        'semana_siguiente_disabled': semana_idx >= len(semanas_mes) - 1,
    }
    
    return render(request, 'Admin/nomina_admin.html', context)

@login_required
def detalle_nomina_vendedor(request, vendedor_id):
    """
    Vista para ver el detalle semanal de un vendedor específico.
    """
    # Verificar permisos
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    from django.contrib.auth.models import User
    
    vendedor = User.objects.get(id=vendedor_id)
    nominas = NominaVendedor.objects.filter(vendedor=vendedor).order_by('-semana_inicio')
    
    context = {
        'vendedor': vendedor,
        'nominas': nominas,
    }
    
    return render(request, 'nomina/detalle_vendedor.html', context)


@login_required
def recalcular_nomina(request):
    """
    Vista para recalcular todas las nóminas (solo admin).
    """
    # Verificar permisos
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'No tienes permisos para esta acción.'})
        messages.error(request, 'No tienes permisos para esta acción.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            resultados = recalcular_todas_nominas()
            mensaje = f'✅ Nómina recalculada correctamente. {len(resultados)} registros actualizados.'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': mensaje})
            else:
                messages.success(request, mensaje)
                return redirect('resumen_nomina')
                
        except Exception as e:
            error_msg = f'❌ Error al recalcular: {str(e)}'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg})
            else:
                messages.error(request, error_msg)
                return redirect('resumen_nomina')
    
    # Si es GET, redirigir al resumen
    return redirect('resumen_nomina')