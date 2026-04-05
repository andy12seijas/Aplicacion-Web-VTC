from django.utils import timezone 
import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

from myapp.forms import InstalacionForm
from .models import *
from django.db.models import Q, Prefetch
from django.core.files.storage import default_storage
from django.contrib.auth.models import User
@login_required
def instalaciones_pendientes(request):
    """Vista para que el instalador vea sus instalaciones pendientes con filtros"""
    
    # Verificar permisos: Superusuario, Administrador o Instalador
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_instalador = request.user.groups.filter(name='Instalador').exists()
    
    if not (es_admin or es_instalador):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Obtener parámetros de filtro
    busqueda = request.GET.get('busqueda', '').strip()
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    filtro_vendedor = request.GET.get('vendedor', '')
    
    # Si es admin, puede ver todas las instalaciones
    if es_admin:
        asignaciones = AsignacionContrato.objects.filter(
            activo=True
        ).select_related(
            'contrato__cliente_potencial',
            'contrato__plan_contratado',
            'venta_directa',
            'cuadrilla',
            'contrato__creado_por'
        ).prefetch_related(
            Prefetch('instalacion', queryset=Instalacion.objects.all())
        ).order_by('fecha_asignacion')
    else:
        # Si es instalador: SOLO ve las instalaciones donde participó o está asignado
        # Esto es clave para que cuando lo saquen de una cuadrilla, siga viendo sus instalaciones
        
        # Opción 1: Ver instalaciones donde participó (históricas)
        instalaciones_del_instalador = Instalacion.objects.filter(
            instaladores=request.user
        ).values_list('asignacion_id', flat=True)
        
        # Opción 2: También ver instalaciones pendientes de su cuadrilla actual
        perfil = request.user.perfil
        cuadrillas_ids = perfil.cuadrillas.filter(activo=True).values_list('id', flat=True)
        
        asignaciones_de_su_cuadrilla = AsignacionContrato.objects.filter(
            cuadrilla_id__in=cuadrillas_ids,
            activo=True
        ).values_list('id', flat=True)
        
        # Combinar ambas: instalaciones donde participó + asignaciones de su cuadrilla actual
        asignaciones_ids = set(list(instalaciones_del_instalador) + list(asignaciones_de_su_cuadrilla))
        
        asignaciones = AsignacionContrato.objects.filter(
            id__in=asignaciones_ids,
            activo=True
        ).select_related(
            'contrato__cliente_potencial',
            'contrato__plan_contratado',
            'venta_directa',
            'cuadrilla',
            'contrato__creado_por'
        ).prefetch_related(
            Prefetch('instalacion', queryset=Instalacion.objects.all())
        ).order_by('fecha_asignacion')
    
    # ===== APLICAR FILTROS =====
    if busqueda:
        asignaciones = asignaciones.filter(
            Q(contrato__cliente_potencial__nombre__icontains=busqueda) |
            Q(contrato__cliente_potencial__apellido__icontains=busqueda) |
            Q(contrato__cliente_potencial__cedula__icontains=busqueda) |
            Q(contrato__customer_id__icontains=busqueda) |
            Q(contrato__ods__icontains=busqueda) |
            Q(venta_directa__nombre__icontains=busqueda) |
            Q(venta_directa__apellido__icontains=busqueda) |
            Q(venta_directa__cedula__icontains=busqueda) |
            Q(venta_directa__customer_id__icontains=busqueda) |
            Q(venta_directa__nro_orden__icontains=busqueda)
        )
    
    if fecha_desde:
        try:
            asignaciones = asignaciones.filter(fecha_asignacion__date__gte=fecha_desde)
        except:
            pass
    
    if fecha_hasta:
        try:
            asignaciones = asignaciones.filter(fecha_asignacion__date__lte=fecha_hasta)
        except:
            pass
    
    if es_admin and filtro_vendedor:
        asignaciones = asignaciones.filter(
            Q(contrato__creado_por_id=filtro_vendedor) |
            Q(venta_directa__creado_por_id=filtro_vendedor)
        )
    
    # Obtener las instalaciones asociadas
    instalaciones_pendientes = []
    instalaciones_completadas = []
    
    for asignacion in asignaciones:
        try:
            instalacion = asignacion.instalacion
            # Para instaladores no-admin, verificar si realmente participaron en la instalación completada
            if not es_admin and instalacion.completada:
                # Solo mostrar si el instalador participó en esta instalación
                if request.user not in instalacion.instaladores.all():
                    continue
            
            if instalacion.completada:
                instalaciones_completadas.append(instalacion)
            else:
                instalaciones_pendientes.append(instalacion)
        except Instalacion.DoesNotExist:
            # Si no existe instalación, crearla automáticamente
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
    paginator_pendientes = Paginator(instalaciones_pendientes, 5)
    page_pendientes = request.GET.get('page_pendientes', 1)
    instalaciones_pendientes_page = paginator_pendientes.get_page(page_pendientes)
    
    paginator_completadas = Paginator(instalaciones_completadas, 5)
    page_completadas = request.GET.get('page_completadas', 1)
    instalaciones_completadas_page = paginator_completadas.get_page(page_completadas)
    
    # Obtener vendedores para el filtro (solo admin)
    vendedores = []
    if es_admin:
        from django.contrib.auth.models import User
        # Usuarios que han creado contratos o ventas directas
        vendedores_ids = set()
        vendedores_ids.update(ContratoCliente.objects.values_list('creado_por_id', flat=True))
        vendedores_ids.update(VentaDirecta.objects.values_list('creado_por_id', flat=True))
        vendedores = User.objects.filter(id__in=vendedores_ids).distinct().order_by('first_name', 'username')
        
    tab_activa = request.GET.get('tab', 'pendientes')
    context = {
        'instalaciones_pendientes': instalaciones_pendientes_page,
        'instalaciones_completadas': instalaciones_completadas_page,
        'total_pendientes': len(instalaciones_pendientes),
        'total_completadas': len(instalaciones_completadas),
        'es_admin': es_admin,
        'busqueda': busqueda,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'filtro_vendedor': filtro_vendedor,
        'vendedores': vendedores,
        'tab_activa': tab_activa,
    }
    return render(request, 'Instaladores/instalaciones_pendientes.html', context)


@login_required
def realizar_instalacion(request, instalacion_id):
    """Vista para realizar una instalación"""
    
    # Verificar permisos
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_instalador = request.user.groups.filter(name='Instalador').exists()
    
    if not (es_admin or es_instalador):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'No tienes permisos para acceder a esta página.'}, status=403)
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Obtener la instalación
    instalacion = get_object_or_404(Instalacion, id=instalacion_id)
    
    # Verificar permisos de instalador
    if es_instalador and not es_admin:
        perfil = request.user.perfil
        cuadrillas_ids = perfil.cuadrillas.filter(activo=True).values_list('id', flat=True)
        
        if instalacion.asignacion.cuadrilla_id not in cuadrillas_ids:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'No tienes permiso para acceder a esta instalación.'}, status=403)
            messages.error(request, 'No tienes permiso para acceder a esta instalación.')
            return redirect('instalaciones_pendientes')
    
    # Verificar que no esté completada
    if instalacion.completada:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Esta instalación ya fue completada.'}, status=400)
        messages.error(request, 'Esta instalación ya fue completada.')
        return redirect('instalaciones_pendientes')
    
    # Obtener la cuadrilla asignada
    cuadrilla = instalacion.asignacion.cuadrilla
    
    # Obtener ubicación de la cuadrilla (promedio de instaladores)
    ubicacion_cuadrilla = None
    if cuadrilla.instaladores.exists():
        ubicaciones = []
        for perfil_instalador in cuadrilla.instaladores.all():
            try:
                # Obtener ubicación del usuario (User, no PerfilUsuario)
                ub = UbicacionUsuario.objects.get(usuario=perfil_instalador.usuario)
                ubicaciones.append((ub.latitud, ub.longitud))
            except UbicacionUsuario.DoesNotExist:
                pass
        
        if ubicaciones:
            lat_promedio = sum(lat for lat, lng in ubicaciones) / len(ubicaciones)
            lng_promedio = sum(lng for lat, lng in ubicaciones) / len(ubicaciones)
            ubicacion_cuadrilla = {'lat': lat_promedio, 'lng': lng_promedio}
    
    # Obtener los instaladores de la cuadrilla (para mostrar en el template)
    # Convertir PerfilUsuario a User para mostrar
    instaladores_de_cuadrilla = [perfil.usuario for perfil in cuadrilla.instaladores.all()]
    
    # Verificar si es una petición AJAX
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.method == 'POST':
        form = InstalacionForm(request.POST, request.FILES, instance=instalacion)
        
        if form.is_valid():
            instalacion = form.save(commit=False)
            
            # Procesar fotos
            fotos_subidas = request.FILES.getlist('fotos')
            fotos_urls = []
            
            for foto in fotos_subidas:
                if not foto.content_type.startswith('image/'):
                    if is_ajax:
                        return JsonResponse({'error': f'El archivo {foto.name} no es una imagen válida.'}, status=400)
                    messages.error(request, f'El archivo {foto.name} no es una imagen válida.')
                    return redirect('realizar_instalacion', instalacion_id=instalacion.id)
                
                if foto.size > 5 * 1024 * 1024:
                    if is_ajax:
                        return JsonResponse({'error': f'El archivo {foto.name} excede el tamaño máximo de 5MB.'}, status=400)
                    messages.error(request, f'El archivo {foto.name} excede el tamaño máximo de 5MB.')
                    return redirect('realizar_instalacion', instalacion_id=instalacion.id)
                
                # Guardar la foto
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                filename = f'instalaciones/instalacion_{instalacion.id}_{timestamp}_{foto.name}'
                saved_path = default_storage.save(filename, foto)
                fotos_urls.append(default_storage.url(saved_path))
            
            # Actualizar lista de fotos
            fotos_actuales = instalacion.fotos or []
            fotos_actuales.extend(fotos_urls)
            instalacion.fotos = fotos_actuales
            
            # Guardar la instalación primero
            instalacion.save()
            
            # ========== NUEVO: GUARDAR TODOS LOS INSTALADORES DE LA CUADRILLA ==========
            # Obtener todos los usuarios de los perfiles de la cuadrilla
            usuarios_instaladores = [perfil.usuario for perfil in cuadrilla.instaladores.all()]
            
            # Asignar todos los instaladores de la cuadrilla a esta instalación
            if usuarios_instaladores:
                instalacion.instaladores.set(usuarios_instaladores)
            else:
                # Si por alguna razón no hay instaladores, al menos guardar al usuario actual
                instalacion.instaladores.add(request.user)
            
            # Marcar como completada
            instalacion.completada = True
            instalacion.fecha_instalacion = timezone.now()
            instalacion.save()
            
            # Actualizar estado del contrato a COMPLETADO
            contrato = instalacion.asignacion.contrato
            if contrato:
                contrato.estado = 'COMPLETADO'
                contrato.save()
            
            # ========== ACTUALIZAR ESTADO DE LA CUADRILLA ==========
            # Verificar si la cuadrilla tiene instalaciones pendientes
            # Una instalación pendiente es aquella cuyo contrato está EN_PROCESO
            instalaciones_pendientes = AsignacionContrato.objects.filter(
                cuadrilla=cuadrilla,
                contrato__estado='EN_PROCESO'  # Contratos en proceso = instalaciones pendientes
            ).count()
            
            # Si no tiene instalaciones pendientes, la cuadrilla está disponible
            if instalaciones_pendientes == 0:
                cuadrilla.estado = Cuadrilla.EstadoCuadrilla.DISPONIBLE
                cuadrilla.save(update_fields=['estado'])
                mensaje = f'📌 La cuadrilla {cuadrilla.nombre} ahora está DISPONIBLE. No tiene más instalaciones pendientes.'
                if is_ajax:
                    return JsonResponse({
                        'success': True, 
                        'message': '✅ Instalación completada exitosamente. ' + mensaje
                    })
                messages.info(request, mensaje)
            else:
                # La cuadrilla aún tiene instalaciones pendientes, sigue ocupada
                mensaje = f'📌 La cuadrilla {cuadrilla.nombre} aún tiene {instalaciones_pendientes} instalación(es) pendiente(s).'
                if is_ajax:
                    return JsonResponse({
                        'success': True, 
                        'message': f'✅ Instalación completada exitosamente. {mensaje}'
                    })
                messages.info(request, mensaje)
            
            if is_ajax:
                return JsonResponse({'success': True, 'message': 'Instalación completada exitosamente.'})
            
            messages.success(request, '✅ Instalación completada exitosamente.')
            return redirect('instalaciones_pendientes')
        else:
            # Si el formulario tiene errores
            if is_ajax:
                errors = {}
                for field, error_list in form.errors.items():
                    errors[field] = error_list[0] if error_list else ''
                return JsonResponse({'error': errors}, status=400)
            
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Error en {field}: {error}')
    
    # Si es GET o hay errores, mostrar el formulario
    form = InstalacionForm(instance=instalacion)
    
    # Obtener modelos de modem
    modelos_modem = ModeloModem.objects.filter(activo=True).order_by('nombre')
    
    # Convertir fotos existentes a JSON para el template
    fotos_existentes = json.dumps(instalacion.fotos or [])
    
    # Obtener instaladores que ya están asignados (para mostrar en el template como seleccionados)
    instaladores_seleccionados = list(instalacion.instaladores.values_list('id', flat=True))
    
    context = {
        'form': form,
        'instalacion': instalacion,
        'modelos_modem': modelos_modem,
        'ubicacion_cuadrilla': ubicacion_cuadrilla,
        'fotos_existentes': fotos_existentes,
        'es_admin': es_admin,
        'instaladores_disponibles': instaladores_de_cuadrilla,  # Para mostrar en el template
        'instaladores_seleccionados': instaladores_seleccionados,  # Para marcar los que ya están
    }
    return render(request, 'Instaladores/realizar_instalaciones.html', context)


@login_required
def capturar_ubicacion_instalador(request):
    """API para capturar la ubicación del instalador automáticamente al cargar el formulario"""
    if request.method == 'POST':
        data = json.loads(request.body)
        latitud = data.get('latitud')
        longitud = data.get('longitud')
        
        if latitud and longitud:
            # Guardar la ubicación en la tabla UbicacionUsuario
            ubicacion, created = UbicacionUsuario.objects.update_or_create(
                usuario=request.user,
                defaults={
                    'latitud': latitud,
                    'longitud': longitud
                }
            )
            
            return JsonResponse({
                'success': True,
                'latitud': latitud,
                'longitud': longitud,
                'ultima_actualizacion': ubicacion.ultima_actualizacion.isoformat(),
                'created': created
            })
        else:
            return JsonResponse({'success': False, 'error': 'Coordenadas inválidas'}, status=400)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)



@login_required
def obtener_detalle_instalacion(request, instalacion_id):
    """API para obtener los detalles completos de una instalación"""
    
    try:
        instalacion = get_object_or_404(Instalacion, id=instalacion_id)
        
        # Verificar permisos
        es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
        es_instalador = request.user.groups.filter(name='Instalador').exists()
        
        if not (es_admin or es_instalador):
            return JsonResponse({'error': 'No tienes permisos para ver esta instalación.'}, status=403)
        
        # Si es instalador, verificar que participó en la instalación
        if es_instalador and not es_admin:
            if request.user not in instalacion.instaladores.all():
                return JsonResponse({'error': 'No tienes permiso para ver esta instalación.'}, status=403)
        
        # Construir datos de la instalación
        datos = {
            'id': instalacion.id,
            'orden_servicio': instalacion.orden_servicio,
            'nombre_cliente': instalacion.nombre_cliente,
            'cedula_cliente': instalacion.cedula_cliente,
            'telefono': instalacion.asignacion.telefono_cliente if hasattr(instalacion.asignacion, 'telefono_cliente') else 'No disponible',
            'plan': instalacion.plan,
            'cuadrilla': instalacion.asignacion.cuadrilla.nombre,
            'estado': 'Completada' if instalacion.completada else 'Pendiente',
            'fecha_instalacion': instalacion.fecha_instalacion.strftime('%d/%m/%Y %H:%M') if instalacion.fecha_instalacion else 'No registrada',
            'fecha_asignacion': instalacion.asignacion.fecha_asignacion.strftime('%d/%m/%Y %H:%M'),
            'fecha_creacion': instalacion.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            
            # Datos técnicos
            'latitud': instalacion.latitud,
            'longitud': instalacion.longitud,
            'feeder': instalacion.feeder or 'No registrado',
            'caja': instalacion.caja or 'No registrado',
            'puerto_utilizado': instalacion.puerto_utilizado or 'No registrado',
            
            # Datos del equipo
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
            
            # Observaciones y fotos
            'observacion': instalacion.observacion or 'Sin observaciones',
            'fotos': instalacion.fotos or [],
            
            # Instaladores que participaron
            'instaladores': [
                {
                    'id': inst.id,
                    'nombre': inst.get_full_name() or inst.username,
                    'username': inst.username
                }
                for inst in instalacion.instaladores.all()
            ],
            
            # Información de origen
            'tipo': 'Contrato' if instalacion.asignacion.contrato else 'Venta Directa',
            'creado_por': instalacion.creado_por.get_full_name() or instalacion.creado_por.username if instalacion.creado_por else 'Sistema',
            'customer_id': instalacion.customer_id,
            'atr': instalacion.atr,
        }
        
        return JsonResponse({'success': True, 'data': datos})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

