from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import ContratoCliente, Cuadrilla, PerfilUsuario
from .forms import AsignacionContratoForm
from .models import AsignacionContrato

def es_admin(user):
    """Verifica si el usuario es administrador"""
    return user.is_superuser or (hasattr(user, 'perfil') and user.perfil.rol == 'ADMIN')

@login_required
@user_passes_test(es_admin)
def lista_asignaciones(request):
    """Vista para listar contratos asignados y no asignados"""
    
    # Obtener IDs de contratos que ya tienen asignación activa
    from .models import AsignacionContrato
    contratos_asignados_ids = AsignacionContrato.objects.filter(
        activo=True
    ).values_list('contrato_id', flat=True)
    
    # Contratos NO ASIGNADOS: Completados (con customer_id y ods) y SIN asignación activa
    contratos_no_asignados = ContratoCliente.objects.filter(
        customer_id__isnull=False,
        ods__isnull=False
    ).exclude(
        customer_id=''
    ).exclude(
        ods=''
    ).exclude(  # ← NUEVO: Excluir los que ya están asignados
        id__in=contratos_asignados_ids
    ).select_related(
        'cliente_potencial', 'creado_por', 'plan_contratado'
    ).order_by('-fecha_creacion')
    
    # Contratos ASIGNADOS: Los que ya tienen una asignación activa
    contratos_asignados = AsignacionContrato.objects.filter(
        activo=True
    ).select_related(
        'contrato__cliente_potencial',
        'contrato__creado_por',
        'cuadrilla'
    ).order_by('-fecha_asignacion')
    
    # Obtener todas las cuadrillas activas para el modal de asignación
    cuadrillas = Cuadrilla.objects.filter(activo=True).order_by('nombre')
    
    # Parámetros de búsqueda
    busqueda_no_asignados = request.GET.get('busqueda_no_asignados', '')
    busqueda_asignados = request.GET.get('busqueda_asignados', '')
    
    if busqueda_no_asignados:
        contratos_no_asignados = contratos_no_asignados.filter(
            Q(cliente_potencial__nombre__icontains=busqueda_no_asignados) |
            Q(cliente_potencial__apellido__icontains=busqueda_no_asignados) |
            Q(cliente_potencial__cedula__icontains=busqueda_no_asignados) |
            Q(customer_id__icontains=busqueda_no_asignados) |
            Q(ods__icontains=busqueda_no_asignados)
        ).distinct()
    
    if busqueda_asignados:
        contratos_asignados = contratos_asignados.filter(
            Q(contrato__cliente_potencial__nombre__icontains=busqueda_asignados) |
            Q(contrato__cliente_potencial__apellido__icontains=busqueda_asignados) |
            Q(contrato__cliente_potencial__cedula__icontains=busqueda_asignados) |
            Q(contrato__customer_id__icontains=busqueda_asignados) |
            Q(contrato__ods__icontains=busqueda_asignados) |
            Q(cuadrilla__nombre__icontains=busqueda_asignados)
        ).distinct()
    
    # Paginación
    paginator_no_asignados = Paginator(contratos_no_asignados, 10)
    page_no_asignados = request.GET.get('page_no_asignados', 1)
    page_obj_no_asignados = paginator_no_asignados.get_page(page_no_asignados)
    
    paginator_asignados = Paginator(contratos_asignados, 10)
    page_asignados = request.GET.get('page_asignados', 1)
    page_obj_asignados = paginator_asignados.get_page(page_asignados)
    
    context = {
        'contratos_no_asignados': page_obj_no_asignados,
        'contratos_asignados': page_obj_asignados,
        'cuadrillas': cuadrillas,
        'busqueda_no_asignados': busqueda_no_asignados,
        'busqueda_asignados': busqueda_asignados,
        'total_no_asignados': contratos_no_asignados.count(),
        'total_asignados': contratos_asignados.count(),
    }
    return render(request, 'Admin/asignacion/asignacion_contrato.html', context)

@login_required
@user_passes_test(es_admin)
def asignar_contrato(request, contrato_id):
    """Vista para asignar un contrato a una cuadrilla"""
    if request.method == 'POST':
        contrato = get_object_or_404(ContratoCliente, id=contrato_id)
        cuadrilla_id = request.POST.get('cuadrilla')
        
        if not cuadrilla_id:
            messages.error(request, '❌ Debe seleccionar una cuadrilla')
            return redirect('lista_asignaciones')
        
        cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id, activo=True)
        
        # Verificar si ya existe una asignación
        from .models import AsignacionContrato
        asignacion_existente = AsignacionContrato.objects.filter(
            contrato=contrato,
            activo=True
        ).first()
        
        if asignacion_existente:
            messages.warning(request, f'⚠️ Este contrato ya está asignado a la cuadrilla {asignacion_existente.cuadrilla.nombre}')
            return redirect('lista_asignaciones')
        
        # Crear nueva asignación
        AsignacionContrato.objects.create(
            contrato=contrato,
            cuadrilla=cuadrilla,
            asignado_por=request.user
        )
        
        messages.success(request, f'✅ Contrato asignado correctamente a la cuadrilla {cuadrilla.nombre}')
        return redirect('lista_asignaciones')
    
    return redirect('lista_asignaciones')


@login_required
@user_passes_test(es_admin)
def desasignar_contrato(request, asignacion_id):
    """Vista para desasignar un contrato (eliminación física)"""
    if request.method == 'POST':
       
        try:
            asignacion = AsignacionContrato.objects.get(id=asignacion_id)
            
            # Verificar si el contrato ya está completado
            if asignacion.contrato.estado == 'COMPLETADO':
                messages.error(request, '❌ No se puede desasignar un contrato que ya está completado')
                return redirect('lista_asignaciones')
            
            # Guardar información para el mensaje antes de eliminar
            contrato_info = f"{asignacion.contrato.cliente_potencial.nombre} {asignacion.contrato.cliente_potencial.apellido}"
            cuadrilla_info = asignacion.cuadrilla.nombre
            
            # Eliminar la asignación completamente
            asignacion.delete()
            
            messages.success(request, f'✅ Contrato de {contrato_info} desasignado de la cuadrilla {cuadrilla_info}. Ya puedes reasignarlo.')
            
        except AsignacionContrato.DoesNotExist:
            messages.error(request, '❌ La asignación no existe')
            
        return redirect('lista_asignaciones')
    
    return redirect('lista_asignaciones')