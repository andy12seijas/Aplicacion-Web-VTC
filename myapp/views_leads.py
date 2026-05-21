# ==================== CALL CENTER - LEADS (INTERESADOS) ====================

from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json

from myapp.decorators import admin_required
from myapp.models import ClientePotencial, LeadInteresado
from myapp.views_instalacion_admin import es_admin  # Ajusta la ruta según tu estructura


@staff_member_required
def panel_leads(request):
    """Panel para que el call center vea y gestione los leads de la web"""
    
    # Obtener parámetros de la URL
    busqueda = request.GET.get('busqueda', '')
    filtro_estado = request.GET.get('estado', '')
    tab_activa = request.GET.get('tab', 'nuevos')  # nuevos, seguimiento, convertidos
    
    # Obtener página actual para cada tabla
    page_nuevos = request.GET.get('page_nuevos', 1)
    page_seguimiento = request.GET.get('page_seguimiento', 1)
    page_convertidos = request.GET.get('page_convertidos', 1)
    
    # ========== LEADS NUEVOS (estado NUEVO y CONTACTADO) ==========
    leads_nuevos = LeadInteresado.objects.filter(estado__in=['NUEVO', 'CONTACTADO']).order_by('-fecha_creacion')
    
    # ========== LEADS EN SEGUIMIENTO ==========
    leads_seguimiento = LeadInteresado.objects.filter(estado='EN_SEGUIMIENTO').order_by('-fecha_creacion')
    
    # ========== LEADS CONVERTIDOS ==========
    leads_convertidos = LeadInteresado.objects.filter(estado='CONVERTIDO').order_by('-fecha_creacion')
    
    # ========== LEADS PERDIDOS (solo para filtro) ==========
    leads_perdidos = LeadInteresado.objects.filter(estado='PERDIDO').order_by('-fecha_creacion')
    
    # Aplicar filtro de búsqueda a todas las listas
    if busqueda:
        leads_nuevos = leads_nuevos.filter(
            Q(nombre__icontains=busqueda) |
            Q(telefono__icontains=busqueda) |
            Q(mensaje__icontains=busqueda)
        )
        leads_seguimiento = leads_seguimiento.filter(
            Q(nombre__icontains=busqueda) |
            Q(telefono__icontains=busqueda) |
            Q(mensaje__icontains=busqueda)
        )
        leads_convertidos = leads_convertidos.filter(
            Q(nombre__icontains=busqueda) |
            Q(telefono__icontains=busqueda) |
            Q(mensaje__icontains=busqueda)
        )
        leads_perdidos = leads_perdidos.filter(
            Q(nombre__icontains=busqueda) |
            Q(telefono__icontains=busqueda) |
            Q(mensaje__icontains=busqueda)
        )
    
    # Si hay filtro de estado específico, mostrar solo ese estado en la tabla correspondiente
    if filtro_estado == 'PERDIDO':
        # Mostrar perdidos en una tabla separada
        leads_perdidos_list = leads_perdidos
    else:
        leads_perdidos_list = LeadInteresado.objects.none()
    
    # Paginación - NUEVOS
    paginator_nuevos = Paginator(leads_nuevos, 15)
    try:
        leads_nuevos_page = paginator_nuevos.page(page_nuevos)
    except (PageNotAnInteger, EmptyPage):
        leads_nuevos_page = paginator_nuevos.page(1)
    
    # Paginación - SEGUIMIENTO
    paginator_seguimiento = Paginator(leads_seguimiento, 15)
    try:
        leads_seguimiento_page = paginator_seguimiento.page(page_seguimiento)
    except (PageNotAnInteger, EmptyPage):
        leads_seguimiento_page = paginator_seguimiento.page(1)
    
    # Paginación - CONVERTIDOS
    paginator_convertidos = Paginator(leads_convertidos, 15)
    try:
        leads_convertidos_page = paginator_convertidos.page(page_convertidos)
    except (PageNotAnInteger, EmptyPage):
        leads_convertidos_page = paginator_convertidos.page(1)
    
    # Paginación - PERDIDOS (para filtro)
    paginator_perdidos = Paginator(leads_perdidos_list, 15)
    try:
        leads_perdidos_page = paginator_perdidos.page(request.GET.get('page_perdidos', 1))
    except (PageNotAnInteger, EmptyPage):
        leads_perdidos_page = paginator_perdidos.page(1)
    
    # Estadísticas
    stats = {
        'nuevos': LeadInteresado.objects.filter(estado='NUEVO').count(),
        'contactados': LeadInteresado.objects.filter(estado='CONTACTADO').count(),
        'en_seguimiento': LeadInteresado.objects.filter(estado='EN_SEGUIMIENTO').count(),
        'convertidos': LeadInteresado.objects.filter(estado='CONVERTIDO').count(),
        'perdidos': LeadInteresado.objects.filter(estado='PERDIDO').count(),
        'total': LeadInteresado.objects.count(),
    }
    
    context = {
        'leads_nuevos': leads_nuevos_page,
        'leads_seguimiento': leads_seguimiento_page,
        'leads_convertidos': leads_convertidos_page,
        'leads_perdidos': leads_perdidos_page,
        'stats': stats,
        'busqueda': busqueda,
        'filtro_estado': filtro_estado,
        'tab_activa': tab_activa,
    }
    
    return render(request, 'pagos/panel_leads.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def cambiar_estado_lead(request, lead_id):
    """API para cambiar el estado de un lead"""
    try:
        lead = get_object_or_404(LeadInteresado, id=lead_id)
        data = json.loads(request.body)
        nuevo_estado = data.get('estado')
        
        # Validar que el estado sea válido
        estados_validos = ['NUEVO', 'CONTACTADO', 'EN_SEGUIMIENTO', 'CONVERTIDO', 'PERDIDO']
        
        if nuevo_estado not in estados_validos:
            return JsonResponse({'success': False, 'error': 'Estado no válido'}, status=400)
        
        # Si el estado es CONTACTADO, registrar la fecha
        if nuevo_estado == 'CONTACTADO' and lead.estado != 'CONTACTADO':
            lead.fecha_contactado = timezone.now()
            lead.contactado_por = request.user
        
        lead.estado = nuevo_estado
        lead.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Lead movido a {lead.get_estado_display()}',
            'nuevo_estado': nuevo_estado,
            'estado_display': lead.get_estado_display()
        })
        
    except LeadInteresado.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Lead no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def agregar_nota_lead(request, lead_id):
    """API para agregar notas de seguimiento a un lead"""
    try:
        lead = get_object_or_404(LeadInteresado, id=lead_id)
        data = json.loads(request.body)
        nota = data.get('nota', '').strip()
        
        if not nota:
            return JsonResponse({'success': False, 'error': 'La nota no puede estar vacía'}, status=400)
        
        fecha = timezone.now().strftime("%d/%m/%Y %H:%M")
        nueva_nota = f"[{fecha}] {request.user.get_full_name() or request.user.username}: {nota}\n"
        
        if lead.notas_seguimiento:
            lead.notas_seguimiento = nueva_nota + lead.notas_seguimiento
        else:
            lead.notas_seguimiento = nueva_nota
        
        lead.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Nota agregada correctamente',
            'notas': lead.notas_seguimiento
        })
        
    except LeadInteresado.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Lead no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def ver_detalle_lead(request, lead_id):
    """Vista para ver el detalle de un lead (usado en el modal)"""
    lead = get_object_or_404(LeadInteresado, id=lead_id)
    
    data = {
        'id': lead.id,
        'nombre': lead.nombre,
        'telefono': lead.telefono,
        'mensaje': lead.mensaje or 'Sin mensaje',
        'estado': lead.estado,
        'estado_display': lead.get_estado_display(),
        'fecha_creacion': lead.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
        'fecha_contactado': lead.fecha_contactado.strftime("%d/%m/%Y %H:%M") if lead.fecha_contactado else None,
        'contactado_por': lead.contactado_por.get_full_name() or lead.contactado_por.username if lead.contactado_por else None,
        'notas_seguimiento': lead.notas_seguimiento or 'No hay notas de seguimiento',
    }
    
    return JsonResponse(data)
from django.contrib.auth.decorators import login_required, user_passes_test

@csrf_exempt
@login_required
def convertir_lead_cliente(request, lead_id):
    """API para marcar un lead como CONVERTIDO"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        lead = get_object_or_404(LeadInteresado, id=lead_id)
        
        # Solo cambiar el estado a CONVERTIDO
        lead.estado = LeadInteresado.EstadoLead.CONVERTIDO
        lead.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Lead marcado como CONVERTIDO exitosamente'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    



from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from myapp.models import RegistroLlamada, SoporteCliente, ReportePago, User
import json
import pytz

@login_required
def reporte_estadisticas_callcenter(request):
    """
    Reporte estadístico del Call Center por semana (viernes a jueves)
    Muestra: llamadas realizadas, soportes leídos, pagos reportados, etc.
    """
    
    VE_TZ = pytz.timezone('America/Caracas')
    
    # Obtener parámetros
    semana_offset = int(request.GET.get('semana_offset', 0))
    agente_id = request.GET.get('agente', '')
    
    # Obtener fecha actual en Venezuela
    ahora_ve = datetime.now().astimezone(VE_TZ)
    hoy_ve = ahora_ve.date()
    
    # Calcular semana (viernes a jueves)
    dias_desde_viernes = (hoy_ve.weekday() - 4) % 7
    viernes_actual = hoy_ve - timedelta(days=dias_desde_viernes)
    
    viernes_seleccionado = viernes_actual - timedelta(weeks=semana_offset)
    jueves_seleccionado = viernes_seleccionado + timedelta(days=6)
    
    # Crear fechas aware para filtrar
    fecha_inicio_aware = VE_TZ.localize(datetime.combine(viernes_seleccionado, datetime.min.time()))
    fecha_fin_aware = VE_TZ.localize(datetime.combine(jueves_seleccionado, datetime.max.time()))
    
    # ========== 1. ESTADÍSTICAS DE LLAMADAS ==========
    llamadas_base = RegistroLlamada.objects.filter(
        fecha_llamada__gte=fecha_inicio_aware,
        fecha_llamada__lte=fecha_fin_aware
    )
    
    if agente_id:
        llamadas_base = llamadas_base.filter(realizado_por_id=agente_id)
    
    total_llamadas = llamadas_base.count()
    llamadas_contactados = llamadas_base.filter(estado='CONTACTADO').count()
    llamadas_no_responde = llamadas_base.filter(estado='NO_RESPONDE').count()
    llamadas_pendientes = llamadas_base.filter(estado='PENDIENTE').count()
    
    # Tasa de efectividad
    tasa_efectividad = (llamadas_contactados / total_llamadas * 100) if total_llamadas > 0 else 0
    
    # Llamadas por día de la semana
    llamadas_por_dia = []
    dias_semana = ['Viernes', 'Sábado', 'Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves']
    
    for i, dia in enumerate(dias_semana):
        fecha_dia = viernes_seleccionado + timedelta(days=i)
        fecha_inicio_dia = VE_TZ.localize(datetime.combine(fecha_dia, datetime.min.time()))
        fecha_fin_dia = VE_TZ.localize(datetime.combine(fecha_dia, datetime.max.time()))
        
        conteo = RegistroLlamada.objects.filter(
            fecha_llamada__gte=fecha_inicio_dia,
            fecha_llamada__lte=fecha_fin_dia
        )
        if agente_id:
            conteo = conteo.filter(realizado_por_id=agente_id)
        
        llamadas_por_dia.append(conteo.count())
    
    # ========== 2. ESTADÍSTICAS DE SOPORTES LEÍDOS ==========
    soportes_base = SoporteCliente.objects.filter(
        fecha_leido__gte=fecha_inicio_aware,
        fecha_leido__lte=fecha_fin_aware,
        estado='LEIDO'
    )
    
    total_soportes_leidos = soportes_base.count()
    
    # Soportes por tipo de cliente
    soportes_internos = soportes_base.filter(tipo_cliente='INTERNO').count()
    soportes_externos = soportes_base.filter(tipo_cliente='EXTERNO').count()
    
    # ========== 3. ESTADÍSTICAS DE PAGOS REPORTADOS ==========
    pagos_base = ReportePago.objects.filter(
        fecha_reporte__gte=fecha_inicio_aware,
        fecha_reporte__lte=fecha_fin_aware
    )
    
    total_pagos = pagos_base.count()
    pagos_verificados = pagos_base.filter(estado='VERIFICADO').count()
    pagos_rechazados = pagos_base.filter(estado='RECHAZADO').count()
    pagos_aplicados = pagos_base.filter(estado='APLICADO').count()
    pagos_pendientes = pagos_base.filter(estado='PENDIENTE').count()
    
    # Pagos por medio
    pagos_pago_movil = pagos_base.filter(medio_pago='PAGO_MOVIL').count()
    pagos_transferencia = pagos_base.filter(medio_pago='TRANSFERENCIA').count()
    
    # ========== 4. RENDIMIENTO POR AGENTE ==========
    agentes = User.objects.filter(
        groups__name='Call Center',
        is_active=True
    ).annotate(
        total_llamadas=Count('llamadas_realizadas', filter=Q(llamadas_realizadas__fecha_llamada__gte=fecha_inicio_aware, llamadas_realizadas__fecha_llamada__lte=fecha_fin_aware)),
        contactados=Count('llamadas_realizadas', filter=Q(llamadas_realizadas__estado='CONTACTADO', llamadas_realizadas__fecha_llamada__gte=fecha_inicio_aware, llamadas_realizadas__fecha_llamada__lte=fecha_fin_aware)),
        no_responde=Count('llamadas_realizadas', filter=Q(llamadas_realizadas__estado='NO_RESPONDE', llamadas_realizadas__fecha_llamada__gte=fecha_inicio_aware, llamadas_realizadas__fecha_llamada__lte=fecha_fin_aware)),
        soportes_leidos=Count('soportes_cliente_creados', filter=Q(soportes_cliente_creados__fecha_leido__gte=fecha_inicio_aware, soportes_cliente_creados__fecha_leido__lte=fecha_fin_aware, soportes_cliente_creados__estado='LEIDO')),
        pagos_validados=Count('reportes_verificados', filter=Q(reportes_verificados__fecha_verificacion__gte=fecha_inicio_aware, reportes_verificados__fecha_verificacion__lte=fecha_fin_aware))
    ).order_by('-total_llamadas')
    
    agentes_data = []
    for agente in agentes:
        efectividad = (agente.contactados / agente.total_llamadas * 100) if agente.total_llamadas > 0 else 0
        agentes_data.append({
            'id': agente.id,
            'nombre': agente.get_full_name() or agente.username,
            'total_llamadas': agente.total_llamadas,
            'contactados': agente.contactados,
            'no_responde': agente.no_responde,
            'efectividad': round(efectividad, 1),
            'soportes_leidos': agente.soportes_leidos,
            'pagos_validados': agente.pagos_validados,
        })
    
    # ========== 5. LLAMADAS POR MES (últimos 6 meses) ==========
    meses = []
    llamadas_por_mes = []
    contactados_por_mes = []
    
    for i in range(5, -1, -1):
        fecha_inicio_mes = (hoy_ve.replace(day=1) - timedelta(days=30*i))
        fecha_fin_mes = (fecha_inicio_mes.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        
        fecha_inicio_mes_aware = VE_TZ.localize(datetime.combine(fecha_inicio_mes, datetime.min.time()))
        fecha_fin_mes_aware = VE_TZ.localize(datetime.combine(fecha_fin_mes, datetime.max.time()))
        
        llamadas_mes = RegistroLlamada.objects.filter(
            fecha_llamada__gte=fecha_inicio_mes_aware,
            fecha_llamada__lte=fecha_fin_mes_aware
        )
        contactados_mes = llamadas_mes.filter(estado='CONTACTADO')
        
        if agente_id:
            llamadas_mes = llamadas_mes.filter(realizado_por_id=agente_id)
            contactados_mes = contactados_mes.filter(realizado_por_id=agente_id)
        
        meses.append(fecha_inicio_mes.strftime('%b'))
        llamadas_por_mes.append(llamadas_mes.count())
        contactados_por_mes.append(contactados_mes.count())
    
    # ========== 6. ÚLTIMAS LLAMADAS ==========
    ultimas_llamadas = llamadas_base.select_related(
        'contrato__cliente_potencial',
        'cliente_potencial',
        'cliente_externo',
        'realizado_por'
    ).order_by('-fecha_llamada')[:15]
    
    ultimas_llamadas_data = []
    for llamada in ultimas_llamadas:
        if llamada.contrato:
            nombre = llamada.contrato.nombre_completo
        elif llamada.cliente_potencial:
            nombre = llamada.cliente_potencial.nombre_completo
        elif llamada.cliente_externo:
            nombre = llamada.cliente_externo.nombre_completo
        else:
            nombre = 'N/A'
        
        ultimas_llamadas_data.append({
            'nombre': nombre,
            'telefono': llamada.telefono_cliente,
            'estado': llamada.get_estado_display(),
            'fecha': llamada.fecha_llamada.astimezone(VE_TZ).strftime('%d/%m/%Y %H:%M'),
            'agente': llamada.realizado_por.get_full_name() or llamada.realizado_por.username if llamada.realizado_por else 'Sistema',
            'nota': llamada.nota[:50] if llamada.nota else ''
        })
    
    # ========== 7. LISTA DE AGENTES ==========
    agentes_lista = User.objects.filter(groups__name='Call Center', is_active=True).order_by('first_name', 'username')
    
    context = {
        # Fechas
        'semana_inicio': viernes_seleccionado.strftime('%d/%m/%Y'),
        'semana_fin': jueves_seleccionado.strftime('%d/%m/%Y'),
        'semana_offset': semana_offset,
        'agente_seleccionado': agente_id,
        'agentes_lista': agentes_lista,
        
        # Estadísticas de llamadas
        'total_llamadas': total_llamadas,
        'llamadas_contactados': llamadas_contactados,
        'llamadas_no_responde': llamadas_no_responde,
        'llamadas_pendientes': llamadas_pendientes,
        'tasa_efectividad': round(tasa_efectividad, 1),
        'llamadas_por_dia': llamadas_por_dia,
        'dias_semana': dias_semana,
        
        # Estadísticas de soportes
        'total_soportes_leidos': total_soportes_leidos,
        'soportes_internos': soportes_internos,
        'soportes_externos': soportes_externos,
        
        # Estadísticas de pagos
        'total_pagos': total_pagos,
        'pagos_verificados': pagos_verificados,
        'pagos_rechazados': pagos_rechazados,
        'pagos_aplicados': pagos_aplicados,
        'pagos_pendientes': pagos_pendientes,
        'pagos_pago_movil': pagos_pago_movil,
        'pagos_transferencia': pagos_transferencia,
        
        # Gráficas
        'meses': json.dumps(meses),
        'llamadas_por_mes': json.dumps(llamadas_por_mes),
        'contactados_por_mes': json.dumps(contactados_por_mes),
        
        # Agentes
        'agentes_data': agentes_data,
        
        # Últimas llamadas
        'ultimas_llamadas': ultimas_llamadas_data,
    }
    
    return render(request, 'pagos/reporte_estadisticas.html', context)    

