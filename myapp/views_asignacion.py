from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import ContratoCliente, Cuadrilla, PerfilUsuario, VentaDirecta
from .forms import AsignacionContratoForm
from .models import AsignacionContrato

def es_admin(user):
    """Verifica si el usuario es administrador"""
    return user.is_superuser or (hasattr(user, 'perfil') and user.perfil.rol == 'ADMIN')

@login_required
@user_passes_test(es_admin)
def lista_asignaciones(request):
    """Vista para listar contratos y ventas directas asignados y no asignados"""
    
    from .models import AsignacionContrato, VentaDirecta
    
    # Obtener parámetros de la URL
    tab_activa = request.GET.get('tab', 'no_asignados')  # 'no_asignados' o 'asignados'
    page_no_asignados = request.GET.get('page_no_asignados', 1)
    page_asignados = request.GET.get('page_asignados', 1)
    
    # ========== CONTRATOS DE VENDEDOR ==========
    contratos_asignados_ids = AsignacionContrato.objects.filter(
        activo=True,
        contrato__isnull=False
    ).values_list('contrato_id', flat=True)
    
    contratos_no_asignados = ContratoCliente.objects.filter(
        customer_id__isnull=False,
        ods__isnull=False
    ).exclude(
        customer_id=''
    ).exclude(
        ods=''
    ).exclude(
        id__in=contratos_asignados_ids
    ).select_related(
        'cliente_potencial', 'creado_por', 'plan_contratado'
    ).order_by('-fecha_creacion')
    
    # ========== VENTAS DIRECTAS ==========
    ventas_asignadas_ids = AsignacionContrato.objects.filter(
        activo=True,
        venta_directa__isnull=False
    ).values_list('venta_directa_id', flat=True)
    
    ventas_no_asignadas = VentaDirecta.objects.filter(
        estado='EN_PROCESO'
    ).exclude(
        id__in=ventas_asignadas_ids
    ).select_related(
        'plan', 'creado_por'
    ).order_by('-fecha_creacion')
    
    # ========== CONTENEDOR UNIFICADO DE "NO ASIGNADOS" ==========
    no_asignados = []
    
    for contrato in contratos_no_asignados:
        no_asignados.append({
            'tipo': 'contrato',
            'id': contrato.id,
            'cliente_nombre': contrato.nombre_completo,
            'cedula': contrato.cedula,
            'correo': contrato.correo_electronico,
            'customer_id': contrato.customer_id,
            'ods': contrato.ods,
            'vendedor': contrato.creado_por.get_full_name() or contrato.creado_por.username if contrato.creado_por else 'Sistema',
            'plan': contrato.plan_contratado.nombre,
            'objeto': contrato
        })
    
    for venta in ventas_no_asignadas:
        no_asignados.append({
            'tipo': 'venta_directa',
            'id': venta.id,
            'cliente_nombre': venta.nombre_completo,
            'cedula': venta.cedula,
            'correo': 'N/A',
            'customer_id': venta.customer_id or '',
            'ods': venta.nro_orden,
            'vendedor': venta.creado_por.get_full_name() or venta.creado_por.username if venta.creado_por else 'Sistema',
            'plan': venta.plan.nombre,
            'objeto': venta
        })
    
    no_asignados.sort(key=lambda x: x['objeto'].fecha_creacion, reverse=True)
    
    # ========== ASIGNADOS (UNIFICADOS) ==========
    asignaciones = AsignacionContrato.objects.filter(
        activo=True
    ).select_related(
        'contrato__cliente_potencial',
        'contrato__creado_por',
        'venta_directa',
        'cuadrilla'
    ).order_by('-fecha_asignacion')
    
    asignados = []
    for asignacion in asignaciones:
        if asignacion.contrato:
            asignados.append({
                'tipo': 'contrato',
                'id': asignacion.id,
                'asignacion_obj': asignacion,
                'cliente_nombre': asignacion.contrato.nombre_completo,
                'cedula': asignacion.contrato.cedula,
                'correo': asignacion.contrato.correo_electronico,
                'customer_id': asignacion.contrato.customer_id,
                'ods': asignacion.contrato.ods,
                'vendedor': asignacion.contrato.creado_por.get_full_name() or asignacion.contrato.creado_por.username if asignacion.contrato.creado_por else 'Sistema',
                'plan': asignacion.contrato.plan_contratado.nombre,
                'estado': asignacion.contrato.estado,
                'cuadrilla': asignacion.cuadrilla,
                'fecha_asignacion': asignacion.fecha_asignacion
            })
        else:
            asignados.append({
                'tipo': 'venta_directa',
                'id': asignacion.id,
                'asignacion_obj': asignacion,
                'cliente_nombre': asignacion.venta_directa.nombre_completo,
                'cedula': asignacion.venta_directa.cedula,
                'correo': '',
                'customer_id': asignacion.venta_directa.customer_id or '',
                'ods': asignacion.venta_directa.nro_orden, 
                'vendedor': asignacion.venta_directa.creado_por.get_full_name() or asignacion.venta_directa.creado_por.username if asignacion.venta_directa.creado_por else 'Sistema',
                'plan': asignacion.venta_directa.plan.nombre,
                'estado': asignacion.venta_directa.estado,
                'cuadrilla': asignacion.cuadrilla,
                'fecha_asignacion': asignacion.fecha_asignacion
            })
    
    # ========== OBTENER CUADRILLAS ==========
    cuadrillas = Cuadrilla.objects.filter(
        activo=True
    ).exclude(
        estado='INACTIVO'
    ).order_by('nombre')
    
    # ========== PAGINACIÓN ==========
    paginator_no_asignados = Paginator(no_asignados, 10)
    paginator_asignados = Paginator(asignados, 10)
    
    page_no_asignados = request.GET.get('page_no_asignados', 1)
    page_asignados = request.GET.get('page_asignados', 1)
    
    # Obtener la página correcta según la pestaña activa
    if tab_activa == 'no_asignados':
        page_obj_no_asignados = paginator_no_asignados.get_page(page_no_asignados)
        page_obj_asignados = paginator_asignados.get_page(1)
    else:
        page_obj_no_asignados = paginator_no_asignados.get_page(1)
        page_obj_asignados = paginator_asignados.get_page(page_asignados)
    
    context = {
        'contratos_no_asignados': page_obj_no_asignados,
        'contratos_asignados': page_obj_asignados,
        'cuadrillas': cuadrillas,
        'total_no_asignados': len(no_asignados),
        'total_asignados': len(asignados),
        'tab_activa': tab_activa,  # 👈 Pasar la pestaña activa
    }
    
    return render(request, 'Admin/asignacion/asignacion_contrato.html', context)


@login_required
@user_passes_test(es_admin)
def asignar_contrato(request, item_id):
    """Vista para asignar un contrato o venta directa a una cuadrilla"""
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        cuadrilla_id = request.POST.get('cuadrilla')
        observaciones = request.POST.get('observaciones', '')
        
        if not cuadrilla_id:
            messages.error(request, '❌ Debe seleccionar una cuadrilla')
            return redirect('lista_asignaciones')
        
        cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id, activo=True)
        
        if tipo == 'contrato':
            item = get_object_or_404(ContratoCliente, id=item_id)
            # Verificar si ya existe una asignación
            asignacion_existente = AsignacionContrato.objects.filter(
                contrato=item,
                activo=True
            ).first()
            
            if asignacion_existente:
                messages.warning(request, f'⚠️ Este contrato ya está asignado a la cuadrilla {asignacion_existente.cuadrilla.nombre}')
                return redirect('lista_asignaciones')
            
            # Crear nueva asignación para contrato
            AsignacionContrato.objects.create(
                contrato=item,
                cuadrilla=cuadrilla,
                asignado_por=request.user,
                observaciones=observaciones
            )
            mensaje = f'✅ Contrato de {item.nombre_completo} asignado correctamente a la cuadrilla {cuadrilla.nombre}'
            
        elif tipo == 'venta_directa':
            item = get_object_or_404(VentaDirecta, id=item_id)
            # Verificar si ya existe una asignación
            asignacion_existente = AsignacionContrato.objects.filter(
                venta_directa=item,
                activo=True
            ).first()
            
            if asignacion_existente:
                messages.warning(request, f'⚠️ Esta venta directa ya está asignada a la cuadrilla {asignacion_existente.cuadrilla.nombre}')
                return redirect('lista_asignaciones')
            
            # Crear nueva asignación para venta directa
            AsignacionContrato.objects.create(
                venta_directa=item,
                cuadrilla=cuadrilla,
                asignado_por=request.user,
                observaciones=observaciones
            )
            mensaje = f'✅ Venta directa #{item.nro_orden} asignada correctamente a la cuadrilla {cuadrilla.nombre}'
        else:
            messages.error(request, '❌ Tipo de elemento no válido')
            return redirect('lista_asignaciones')
        
        # Cambiar estado de la cuadrilla a OCUPADO si estaba disponible
        if cuadrilla.estado == 'DISPONIBLE':
            cuadrilla.estado = Cuadrilla.EstadoCuadrilla.OCUPADO
            cuadrilla.save(update_fields=['estado'])
            messages.info(request, f'📌 La cuadrilla {cuadrilla.nombre} ahora está OCUPADA')
        
        messages.success(request, mensaje)
        return redirect('lista_asignaciones')
    
    return redirect('lista_asignaciones')

@login_required
@user_passes_test(es_admin)
def desasignar_contrato(request, asignacion_id):
    """Vista para desasignar un contrato o venta directa (eliminación física)"""
    if request.method == 'POST':
        try:
            # Obtener la asignación
            asignacion = AsignacionContrato.objects.get(id=asignacion_id, activo=True)
            
            # Determinar el tipo y verificar estado
            if asignacion.contrato:
                # Es un contrato de vendedor
                if asignacion.contrato.estado == 'COMPLETADO':
                    messages.error(request, '❌ No se puede desasignar un contrato que ya está completado')
                    return redirect('lista_asignaciones')
                item_info = f"contrato de {asignacion.contrato.nombre_completo}"
                estado_item = asignacion.contrato.estado
            elif asignacion.venta_directa:
                # Es una venta directa
                if asignacion.venta_directa.estado == 'COMPLETADO':
                    messages.error(request, '❌ No se puede desasignar una venta directa que ya está completada')
                    return redirect('lista_asignaciones')
                item_info = f"venta directa #{asignacion.venta_directa.nro_orden} - {asignacion.venta_directa.nombre_completo}"
                estado_item = asignacion.venta_directa.estado
            else:
                messages.error(request, '❌ Asignación no válida')
                return redirect('lista_asignaciones')
            
            # Guardar información antes de eliminar
            cuadrilla = asignacion.cuadrilla
            cuadrilla_info = cuadrilla.nombre
            
            # ========== ELIMINAR FÍSICAMENTE LA ASIGNACIÓN ==========
            asignacion.delete()
            
            # ========== VERIFICAR SI LA CUADRILLA TIENE MÁS ASIGNACIONES EN PROCESO ==========
            # Contar solo asignaciones cuyo contrato/venta está EN_PROCESO
            asignaciones_en_proceso = AsignacionContrato.objects.filter(
                cuadrilla=cuadrilla,
                activo=True
            ).filter(
                Q(contrato__estado='EN_PROCESO') |
                Q(venta_directa__estado='EN_PROCESO')
            ).count()
            
            # ========== ACTUALIZAR ESTADO DE LA CUADRILLA ==========
            # Si no tiene asignaciones en proceso, cambiar estado a DISPONIBLE
            if asignaciones_en_proceso == 0:
                cuadrilla.estado = Cuadrilla.EstadoCuadrilla.DISPONIBLE
                cuadrilla.save(update_fields=['estado'])
                messages.info(request, f'📌 La cuadrilla {cuadrilla.nombre} ahora está DISPONIBLE')
            else:
                messages.info(request, f'📌 La cuadrilla {cuadrilla.nombre} aún tiene {asignaciones_en_proceso} asignación(es) en proceso')
            
            messages.success(request, f'✅ {item_info} desasignado de la cuadrilla {cuadrilla_info}')
            
        except AsignacionContrato.DoesNotExist:
            messages.error(request, '❌ La asignación no existe')
        
        return redirect('lista_asignaciones')
    
    return redirect('lista_asignaciones')