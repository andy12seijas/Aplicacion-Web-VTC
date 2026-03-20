from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import AsignacionContrato, Instalacion, ModeloModem
from .forms import InstalacionForm
from django.db.models import Q, Prefetch
@login_required
def instalaciones_pendientes(request):
    """Vista para que el instalador vea sus instalaciones pendientes"""
    
    # Verificar permisos: Superusuario, Administrador o Instalador
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_instalador = request.user.groups.filter(name='Instalador').exists()
    
    if not (es_admin or es_instalador):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Si es admin, puede ver todas las instalaciones
    if es_admin:
        # Obtener todas las asignaciones activas con todos los datos relacionados
        asignaciones = AsignacionContrato.objects.filter(
            activo=True
        ).select_related(
            'contrato__cliente_potencial',
            'contrato__plan_contratado',
            'cuadrilla'
        ).prefetch_related(
            Prefetch('instalacion', queryset=Instalacion.objects.all())
        ).order_by('fecha_asignacion')
    else:
        # Si es instalador, solo ve las de su cuadrilla
        perfil = request.user.perfil
        cuadrillas_ids = perfil.cuadrillas.filter(activo=True).values_list('id', flat=True)
        
        asignaciones = AsignacionContrato.objects.filter(
            cuadrilla_id__in=cuadrillas_ids,
            activo=True
        ).select_related(
            'contrato__cliente_potencial',
            'contrato__plan_contratado',
            'cuadrilla'
        ).prefetch_related(
            Prefetch('instalacion', queryset=Instalacion.objects.all())
        ).order_by('fecha_asignacion')
    
    # Obtener las instalaciones asociadas (algunas pueden estar completadas)
    instalaciones_pendientes = []
    instalaciones_completadas = []
    
    for asignacion in asignaciones:
        try:
            instalacion = asignacion.instalacion
            if instalacion.completada:
                instalaciones_completadas.append(instalacion)
            else:
                instalaciones_pendientes.append(instalacion)
        except Instalacion.DoesNotExist:
            # Si no existe instalación, crearla automáticamente con valores por defecto
            instalacion = Instalacion.objects.create(
                asignacion=asignacion,
                creado_por=request.user if not es_admin else None,
                inicio_fibra=0,
                final_fibra=0,
                conectores=0,
                rosetas=0,
                patch_cord=0,
                tensores=0,
                conectores_malos=0
            )
            instalaciones_pendientes.append(instalacion)
    
    # Ordenar pendientes por fecha de asignación (más antiguas primero)
    instalaciones_pendientes.sort(key=lambda x: x.asignacion.fecha_asignacion)
    
    # Ordenar completadas por fecha de instalación (más recientes primero)
    instalaciones_completadas.sort(key=lambda x: x.fecha_instalacion or x.fecha_creacion, reverse=True)
    
    # Paginación
    paginator_pendientes = Paginator(instalaciones_pendientes, 10)
    page_pendientes = request.GET.get('page_pendientes', 1)
    instalaciones_pendientes_page = paginator_pendientes.get_page(page_pendientes)
    
    paginator_completadas = Paginator(instalaciones_completadas, 10)
    page_completadas = request.GET.get('page_completadas', 1)
    instalaciones_completadas_page = paginator_completadas.get_page(page_completadas)
    
    # Debug: imprimir para verificar
    print(f"Total pendientes: {len(instalaciones_pendientes)}")
    for inst in instalaciones_pendientes[:3]:
        print(f"Instalación {inst.id}: {inst.nombre_cliente} - {inst.customer_id}")
    
    context = {
        'instalaciones_pendientes': instalaciones_pendientes_page,
        'instalaciones_completadas': instalaciones_completadas_page,
        'total_pendientes': len(instalaciones_pendientes),
        'total_completadas': len(instalaciones_completadas),
        'es_admin': es_admin,
    }
    return render(request, 'Instaladores/instalaciones_pendientes.html', context)


@login_required
def realizar_instalacion(request, instalacion_id):
    """Vista para realizar una instalación"""
    
    # Verificar permisos: Superusuario, Administrador o Instalador
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_instalador = request.user.groups.filter(name='Instalador').exists()
    
    if not (es_admin or es_instalador):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Obtener la instalación
    instalacion = get_object_or_404(Instalacion, id=instalacion_id)
    
    # Si es instalador (no admin), verificar que la instalación pertenezca a su cuadrilla
    if es_instalador and not es_admin:
        perfil = request.user.perfil
        cuadrillas_ids = perfil.cuadrillas.filter(activo=True).values_list('id', flat=True)
        
        if instalacion.asignacion.cuadrilla_id not in cuadrillas_ids:
            messages.error(request, 'No tienes permiso para acceder a esta instalación.')
            return redirect('instalaciones_pendientes')
    
    # Verificar que la instalación no esté ya completada
    if instalacion.completada:
        messages.error(request, 'Esta instalación ya fue completada.')
        return redirect('instalaciones_pendientes')
    
    if request.method == 'POST':
        form = InstalacionForm(request.POST, instance=instalacion)
        if form.is_valid():
            instalacion = form.save(commit=False)
            instalacion.completada = True
            instalacion.creado_por = request.user
            instalacion.save()
            
            # Actualizar el estado del contrato a COMPLETADO
            contrato = instalacion.asignacion.contrato
            contrato.estado = 'COMPLETADO'
            contrato.save()
            
            messages.success(request, '✅ Instalación completada exitosamente.')
            return redirect('instalaciones_pendientes')
    else:
        form = InstalacionForm(instance=instalacion)
    
    # Obtener modelos de modem para el select
    modelos_modem = ModeloModem.objects.filter(activo=True).order_by('nombre')
    
    context = {
        'form': form,
        'instalacion': instalacion,
        'modelos_modem': modelos_modem,
        'es_admin': es_admin,
    }
    return render(request, 'Instaladores/realizar_instalaciones.html', context)