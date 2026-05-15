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

from myapp.models import LeadInteresado  # Ajusta la ruta según tu estructura


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