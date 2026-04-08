from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from datetime import datetime

from myapp.models import Instalacion, AsignacionContrato, ContratoCliente, VentaDirecta, ModeloModem, User, Cuadrilla
from myapp.forms import InstalacionEditForm, InstalacionForm

def es_admin(user):
    """Verifica si el usuario es administrador"""
    return user.is_authenticated and (
        user.is_superuser or 
        user.groups.filter(name='Administrador').exists()
    )


@login_required
@user_passes_test(es_admin)
def lista_instalaciones_admin(request):
    """Vista para listar todas las instalaciones (solo admin)"""
    
    # Obtener parámetros de filtro
    busqueda = request.GET.get('busqueda', '')
    estado = request.GET.get('estado', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    cuadrilla_id = request.GET.get('cuadrilla', '')
    
    # Base de consulta
    instalaciones = Instalacion.objects.all().select_related(
        'asignacion',
        'asignacion__cuadrilla',
        'asignacion__contrato__cliente_potencial',
        'asignacion__venta_directa',
        'modelo_modem'
    ).prefetch_related(
        'instaladores'
    ).order_by('-fecha_creacion')
    
    # Aplicar filtros
    if busqueda:
        instalaciones = instalaciones.filter(
            Q(asignacion__contrato__cliente_potencial__nombre__icontains=busqueda) |
            Q(asignacion__contrato__cliente_potencial__apellido__icontains=busqueda) |
            Q(asignacion__contrato__cliente_potencial__cedula__icontains=busqueda) |
            Q(asignacion__venta_directa__nombre__icontains=busqueda) |
            Q(asignacion__venta_directa__apellido__icontains=busqueda) |
            Q(asignacion__venta_directa__cedula__icontains=busqueda) |
            Q(asignacion__contrato__customer_id__icontains=busqueda) |
            Q(asignacion__venta_directa__customer_id__icontains=busqueda)
        )
    
    if estado:
        completada = estado == 'completada'
        instalaciones = instalaciones.filter(completada=completada)
    
    if fecha_desde:
        try:
            instalaciones = instalaciones.filter(fecha_instalacion__date__gte=fecha_desde)
        except:
            pass
    
    if fecha_hasta:
        try:
            instalaciones = instalaciones.filter(fecha_instalacion__date__lte=fecha_hasta)
        except:
            pass
    
    if cuadrilla_id:
        instalaciones = instalaciones.filter(asignacion__cuadrilla_id=cuadrilla_id)
    
    # Estadísticas
    total_instalaciones = instalaciones.count()
    total_completadas = instalaciones.filter(completada=True).count()
    total_pendientes = instalaciones.filter(completada=False).count()
    
    # Paginación
    paginator = Paginator(instalaciones, 5)
    page_number = request.GET.get('page', 1)
    instalaciones_page = paginator.get_page(page_number)
    
    # Lista de cuadrillas para filtro
    cuadrillas = Cuadrilla.objects.filter(activo=True)
    
    context = {
        'instalaciones': instalaciones_page,
        'total_instalaciones': total_instalaciones,
        'total_completadas': total_completadas,
        'total_pendientes': total_pendientes,
        'busqueda': busqueda,
        'estado': estado,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'cuadrilla_id': cuadrilla_id,
        'cuadrillas': cuadrillas,
        'es_admin': True,
    }
    
    return render(request, 'Admin/instalacion/lista_instalacion_admin.html', context)


@login_required
@user_passes_test(es_admin)
@require_http_methods(["GET"])
def detalle_instalacion_json(request, instalacion_id):
    """Retorna los detalles de una instalación en formato JSON para el modal"""
    
    instalacion = get_object_or_404(Instalacion, id=instalacion_id)
    
    # Obtener instaladores
    instaladores_lista = []
    for inst in instalacion.instaladores.all():
        nombre = inst.get_full_name() if inst.get_full_name() else inst.username
        instaladores_lista.append({'id': inst.id, 'nombre': nombre})
    
    # Obtener fotos
    fotos = instalacion.fotos if instalacion.fotos else []
    
    # Determinar origen (contrato o venta directa)
    origen = 'contrato' if instalacion.asignacion.contrato else 'venta_directa'
    
    # Obtener dirección desde la asignación
    direccion = "N/A"
    if instalacion.asignacion.contrato:
        direccion = instalacion.asignacion.contrato.direccion_detallada
    elif instalacion.asignacion.venta_directa:
        direccion = instalacion.asignacion.venta_directa.direccion if hasattr(instalacion.asignacion.venta_directa, 'direccion') else "N/A"
    
    data = {
        'id': instalacion.id,
        'nombre_cliente': instalacion.nombre_cliente,
        'cedula_cliente': instalacion.cedula_cliente,
        'direccion': direccion,  # CORREGIDO: ahora usa la variable direccion
        'plan': instalacion.plan,
        'customer_id': instalacion.customer_id,
        'atr': instalacion.atr,
        'estado': 'Completada' if instalacion.completada else 'Pendiente',
        'completada': instalacion.completada,
        'fecha_instalacion': instalacion.fecha_instalacion.strftime('%d/%m/%Y %H:%M') if instalacion.fecha_instalacion else 'No registrada',
        'fecha_creacion': instalacion.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        'fecha_actualizacion': instalacion.fecha_actualizacion.strftime('%d/%m/%Y %H:%M'),
        
        # Datos técnicos
        'latitud': instalacion.latitud,
        'longitud': instalacion.longitud,
        'feeder': instalacion.feeder or 'N/A',
        'caja': instalacion.caja or 'N/A',
        'puerto_utilizado': instalacion.puerto_utilizado or 'N/A',
        
        # Equipo
        'modelo_modem': instalacion.modelo_modem.nombre if instalacion.modelo_modem else 'No registrado',
        'sn_modem': instalacion.sn_modem or 'No registrado',
        'mac_modem': instalacion.mac_modem or 'No registrado',
        
        # Materiales
        'inicio_fibra': instalacion.inicio_fibra or 0,
        'final_fibra': instalacion.final_fibra or 0,
        'metros_utilizados': instalacion.metros_utilizados,
        'conectores': instalacion.conectores or 0,
        'rosetas': instalacion.rosetas or 0,
        'patch_cord': instalacion.patch_cord or 0,
        'tensores': instalacion.tensores or 0,
        'conectores_malos': instalacion.conectores_malos or 0,
        
        # Fotos
        'fotos': fotos,
        
        # Instaladores
        'instaladores': instaladores_lista,
        
        # Cuadrilla
        'cuadrilla': instalacion.asignacion.cuadrilla.nombre if instalacion.asignacion.cuadrilla else 'No asignada',
        'cuadrilla_codigo': instalacion.asignacion.cuadrilla.codigo if instalacion.asignacion.cuadrilla else 'N/A',
        
        # Observación
        'observacion': instalacion.observacion or 'Sin observaciones',
        
        # Origen
        'origen': origen,
        'orden_servicio': instalacion.orden_servicio,
        
        # Información adicional
        'creado_por': instalacion.creado_por_nombre,
        'creado_por_id': instalacion.creado_por.id if instalacion.creado_por else None,
    }
    
    return JsonResponse(data)


@login_required
@user_passes_test(es_admin)
def editar_instalacion(request, instalacion_id):
    """Editar una instalación existente"""
    
    instalacion = get_object_or_404(Instalacion, id=instalacion_id)
    modelos_modem = ModeloModem.objects.filter(activo=True)
    
    if request.method == 'POST':
        form = InstalacionEditForm(request.POST, request.FILES, instance=instalacion)
        if form.is_valid():
            instalacion = form.save(commit=False)
            
            # Procesar fecha de instalación
            if request.POST.get('fecha_instalacion'):
                try:
                    from django.utils import timezone
                    fecha_str = request.POST.get('fecha_instalacion')
                    instalacion.fecha_instalacion = datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M')
                except:
                    pass
            
            instalacion.save()
            
            # Guardar instaladores (ManyToMany)
            instaladores_ids = request.POST.getlist('instaladores')
            if instaladores_ids:
                instalacion.instaladores.set(instaladores_ids)
            
            # Procesar eliminación de fotos
            fotos_eliminar = request.POST.get('fotos_eliminar', '')
            if fotos_eliminar:
                import json
                fotos_a_eliminar = json.loads(fotos_eliminar)
                from django.core.files.storage import default_storage
                fotos_actuales = instalacion.fotos or []
                for foto_url in fotos_a_eliminar:
                    if foto_url in fotos_actuales:
                        fotos_actuales.remove(foto_url)
                        if '/media/' in foto_url:
                            ruta = foto_url.split('/media/')[-1]
                            if default_storage.exists(ruta):
                                default_storage.delete(ruta)
                instalacion.fotos = fotos_actuales
                instalacion.save()
            
            # Procesar nuevas fotos
            fotos = request.FILES.getlist('fotos_upload')
            if fotos:
                import os
                from django.utils import timezone as tz
                fotos_urls = instalacion.fotos or []
                for foto in fotos:
                    extension = os.path.splitext(foto.name)[1].lower()
                    nombre_archivo = f"instalacion_{instalacion.id}_{int(tz.now().timestamp())}{extension}"
                    ruta = os.path.join('instalaciones', nombre_archivo)
                    from django.core.files.storage import default_storage
                    saved_path = default_storage.save(ruta, foto)
                    fotos_urls.append(default_storage.url(saved_path))
                instalacion.fotos = fotos_urls
                instalacion.save()
            
            messages.success(request, 'Instalación actualizada exitosamente')
            return redirect('lista_instalaciones')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Error en {field}: {error}')
    else:
        form = InstalacionForm(instance=instalacion)
    
    # Obtener instaladores de la cuadrilla para el selector
    cuadrilla = instalacion.asignacion.cuadrilla if instalacion.asignacion.cuadrilla else None
    instaladores_disponibles = []
    if cuadrilla:
        from myapp.models import PerfilUsuario
        perfiles = cuadrilla.instaladores.filter(activo=True)
        instaladores_disponibles = [p.usuario for p in perfiles]
    
    # Instaladores actuales
    instaladores_actuales = list(instalacion.instaladores.all())
    
    context = {
        'form': form,
        'instalacion': instalacion,
        'modelos_modem': modelos_modem,
        'instaladores_disponibles': instaladores_disponibles,
        'instaladores_actuales': instaladores_actuales,
        'fotos_existentes': instalacion.fotos or [],
    }
    
    return render(request, 'Admin/instalacion/editar_instalacion.html', context)