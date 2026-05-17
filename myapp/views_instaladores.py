from django.utils import timezone 
import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models import Prefetch
from myapp.forms import InstalacionForm
from .models import *
from django.db.models import Q, Prefetch
from django.core.files.storage import default_storage
from django.contrib.auth.models import User


@login_required
def instalaciones_pendientes(request):
    """Vista para que el instalador vea sus instalaciones pendientes con filtros"""
    
    import pytz
    from datetime import datetime, timedelta
    
    # Verificar permisos: Superusuario, Administrador o Instalador
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_instalador = request.user.groups.filter(name='Instalador').exists()
    
    if not (es_admin or es_instalador):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Zona horaria de Venezuela
    VE_TZ = pytz.timezone('America/Caracas')
    
    # Obtener parámetros de filtro
    busqueda = request.GET.get('busqueda', '').strip()
    fecha_desde_raw = request.GET.get('fecha_desde', '')
    fecha_hasta_raw = request.GET.get('fecha_hasta', '')
    filtro_vendedor = request.GET.get('vendedor', '')
    
    # ========== CONVERTIR FECHAS A OBJETOS DATE ==========
    fecha_desde_obj = None
    fecha_hasta_obj = None
    
    if fecha_desde_raw:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde_raw, '%Y-%m-%d').date()
        except ValueError:
            try:
                fecha_desde_obj = datetime.strptime(fecha_desde_raw, '%d/%m/%Y').date()
            except ValueError:
                pass
    
    if fecha_hasta_raw:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta_raw, '%Y-%m-%d').date()
        except ValueError:
            try:
                fecha_hasta_obj = datetime.strptime(fecha_hasta_raw, '%d/%m/%Y').date()
            except ValueError:
                pass
    
    # Convertir a datetime aware para filtrar
    fecha_inicio_aware = None
    fecha_fin_aware = None
    
    if fecha_desde_obj:
        fecha_inicio_aware = VE_TZ.localize(datetime.combine(fecha_desde_obj, datetime.min.time()))
    
    if fecha_hasta_obj:
        fecha_fin_aware = VE_TZ.localize(datetime.combine(fecha_hasta_obj, datetime.max.time()))
    
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
        instalaciones_del_instalador = Instalacion.objects.filter(
            instaladores=request.user
        ).values_list('asignacion_id', flat=True)
        
        perfil = request.user.perfil
        cuadrillas_ids = perfil.cuadrillas.filter(activo=True).values_list('id', flat=True)
        
        asignaciones_de_su_cuadrilla = AsignacionContrato.objects.filter(
            cuadrilla_id__in=cuadrillas_ids,
            activo=True
        ).values_list('id', flat=True)
        
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
    
    # ===== APLICAR FILTROS CON DATETIME AWARE =====
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
    
    # FILTRAR POR FECHA USANDO DATETIME AWARE
    if fecha_inicio_aware and fecha_fin_aware:
        asignaciones = asignaciones.filter(
            fecha_asignacion__gte=fecha_inicio_aware,
            fecha_asignacion__lte=fecha_fin_aware
        )
    elif fecha_inicio_aware:
        asignaciones = asignaciones.filter(fecha_asignacion__gte=fecha_inicio_aware)
    elif fecha_fin_aware:
        asignaciones = asignaciones.filter(fecha_asignacion__lte=fecha_fin_aware)
    
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
                if request.user not in instalacion.instaladores.all():
                    continue
            
            # ===== AGREGAR CAMPOS DE UBICACIÓN =====
            # Obtener latitud y longitud desde el contrato o venta directa
            latitud_cliente = 0
            longitud_cliente = 0
            
            if asignacion.contrato:
                latitud_cliente = asignacion.contrato.latitud or 0
                longitud_cliente = asignacion.contrato.longitud or 0
            elif asignacion.venta_directa:
                # Si VentaDirecta tiene campos de ubicación, agrégalos aquí
                # Por ahora usamos 0
                latitud_cliente = 0
                longitud_cliente = 0
            
            # Agregar propiedades a la instalación
            instalacion.latitud_cliente = float(latitud_cliente)
            instalacion.longitud_cliente = float(longitud_cliente)
            instalacion.tiene_ubicacion = (latitud_cliente != 0 and longitud_cliente != 0)
            
            if instalacion.completada:
                instalaciones_completadas.append(instalacion)
            else:
                instalaciones_pendientes.append(instalacion)
        except Instalacion.DoesNotExist:
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
            # También agregar ubicación al nuevo objeto
            if asignacion.contrato:
                instalacion.latitud_cliente = asignacion.contrato.latitud or 0
                instalacion.longitud_cliente = asignacion.contrato.longitud or 0
            else:
                instalacion.latitud_cliente = 0
                instalacion.longitud_cliente = 0
            instalacion.tiene_ubicacion = (instalacion.latitud_cliente != 0 and instalacion.longitud_cliente != 0)
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
        vendedores_ids = set()
        vendedores_ids.update(ContratoCliente.objects.values_list('creado_por_id', flat=True))
        vendedores_ids.update(VentaDirecta.objects.values_list('creado_por_id', flat=True))
        vendedores = User.objects.filter(id__in=vendedores_ids).distinct().order_by('first_name', 'username')
        
    tab_activa = request.GET.get('tab', 'pendientes')
    
    # Para mostrar en el template (mantener las fechas originales)
    fecha_desde_mostrar = fecha_desde_raw
    fecha_hasta_mostrar = fecha_hasta_raw
    
    context = {
        'instalaciones_pendientes': instalaciones_pendientes_page,
        'instalaciones_completadas': instalaciones_completadas_page,
        'total_pendientes': len(instalaciones_pendientes),
        'total_completadas': len(instalaciones_completadas),
        'es_admin': es_admin,
        'busqueda': busqueda,
        'fecha_desde': fecha_desde_mostrar,
        'fecha_hasta': fecha_hasta_mostrar,
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
    
    # ========== OBTENER INVENTARIO DE LA CUADRILLA ==========
    inventario_cuadrilla_raw = {
        "Modem": 0,
        "Conector": 0,
        "Roseta": 0,
        "Patch Cord": 0,
        "Tensor": 0,
        "Fibra Optica (metros)": 0,
        "Tirros": 0,
    }
    
    try:
        materiales_disponibles = InventarioCuadrilla.objects.filter(cuadrilla=cuadrilla).select_related('material')
        for item in materiales_disponibles:
            inventario_cuadrilla_raw[item.material.nombre] = item.cantidad
    except:
        pass
    
    # Transformar claves para el template
    inventario_cuadrilla = {
        "Modem": inventario_cuadrilla_raw.get("Modem", 0),
        "Conector": inventario_cuadrilla_raw.get("Conector", 0),
        "Roseta": inventario_cuadrilla_raw.get("Roseta", 0),
        "Patch_Cord": inventario_cuadrilla_raw.get("Patch Cord", 0),
        "Tensor": inventario_cuadrilla_raw.get("Tensor", 0),
        "metros": inventario_cuadrilla_raw.get("Fibra Optica (metros)", 0),
        "Tirros": inventario_cuadrilla_raw.get("Tirros", 0),
    }
    
    # Obtener ubicación de la cuadrilla (promedio de instaladores)
    ubicacion_cuadrilla = None
    if cuadrilla.instaladores.exists():
        ubicaciones = []
        for perfil_instalador in cuadrilla.instaladores.all():
            try:
                ub = UbicacionUsuario.objects.get(usuario=perfil_instalador.usuario)
                ubicaciones.append((ub.latitud, ub.longitud))
            except UbicacionUsuario.DoesNotExist:
                pass
        
        if ubicaciones:
            lat_promedio = sum(lat for lat, lng in ubicaciones) / len(ubicaciones)
            lng_promedio = sum(lng for lat, lng in ubicaciones) / len(ubicaciones)
            ubicacion_cuadrilla = {'lat': lat_promedio, 'lng': lng_promedio}
    
    # Obtener los instaladores de la cuadrilla
    instaladores_de_cuadrilla = [perfil.usuario for perfil in cuadrilla.instaladores.all()]
    
    # Verificar si es una petición AJAX
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.method == 'POST':
        form = InstalacionForm(request.POST, request.FILES, instance=instalacion)
        
        # ========== OBTENER VALORES DEL POST ==========
        inicio_fibra = int(request.POST.get('inicio_fibra', 0) or 0)
        final_fibra = int(request.POST.get('final_fibra', 0) or 0)
        metros_usados = abs(inicio_fibra - final_fibra)
        
        conectores_usados = int(request.POST.get('conectores', 0) or 0)
        conectores_malos_usados = int(request.POST.get('conectores_malos', 0) or 0)
        conectores_totales = conectores_usados + conectores_malos_usados
        
        rosetas_usadas = int(request.POST.get('rosetas', 0) or 0)
        patch_usados = int(request.POST.get('patch_cord', 0) or 0)
        tensores_usados = int(request.POST.get('tensores', 0) or 0)
        tirros_usados = int(request.POST.get('tirros', 0) or 0)
        modelo_modem_id = request.POST.get('modelo_modem')
        
        # ========== VALIDAR STOCK ANTES DE GUARDAR ==========
        errores_stock = []
        
        # Validar módem
        if modelo_modem_id and modelo_modem_id != '':
            if inventario_cuadrilla.get("Modem", 0) < 1:
                errores_stock.append("No hay módems disponibles en el inventario de la cuadrilla.")
        
        # Validar conectores (incluyendo malos)
        if conectores_totales > inventario_cuadrilla.get("Conector", 0):
            errores_stock.append(f"Stock insuficiente de conectores. Necesitas {conectores_totales} (Buenos: {conectores_usados}, Malos: {conectores_malos_usados}). Disponible: {inventario_cuadrilla.get('Conector', 0)}")
        
        # Validar rosetas
        if rosetas_usadas > inventario_cuadrilla.get("Roseta", 0):
            errores_stock.append(f"Stock insuficiente de rosetas. Disponible: {inventario_cuadrilla.get('Roseta', 0)}")
        
        # Validar patch cord
        if patch_usados > inventario_cuadrilla.get("Patch_Cord", 0):
            errores_stock.append(f"Stock insuficiente de patch cord. Disponible: {inventario_cuadrilla.get('Patch_Cord', 0)}")
        
        # Validar tensores
        if tensores_usados > inventario_cuadrilla.get("Tensor", 0):
            errores_stock.append(f"Stock insuficiente de tensores. Disponible: {inventario_cuadrilla.get('Tensor', 0)}")
        
        # Validar tirros
        if tirros_usados > inventario_cuadrilla.get("Tirros", 0):
            errores_stock.append(f"Stock insuficiente de tirros. Disponible: {inventario_cuadrilla.get('Tirros', 0)}")
        
        # Validar fibra
        if metros_usados > inventario_cuadrilla.get("metros", 0):
            errores_stock.append(f"Stock insuficiente de fibra óptica. Metros disponibles: {inventario_cuadrilla.get('metros', 0)}")
        
        # Si hay errores de stock, mostrar mensajes
        if errores_stock:
            if is_ajax:
                return JsonResponse({'error': '<br>'.join(errores_stock)}, status=400)
            for error in errores_stock:
                messages.error(request, f'❌ {error}')
            return redirect('realizar_instalacion', instalacion_id=instalacion.id)
        
        # ========== VALIDACIÓN ADICIONAL CON BD ==========
        if modelo_modem_id and modelo_modem_id != '':
            inv_modem_bd = InventarioCuadrilla.objects.filter(cuadrilla=cuadrilla, material__nombre="Modem").first()
            if not inv_modem_bd or inv_modem_bd.cantidad < 1:
                if is_ajax:
                    return JsonResponse({'error': 'No hay módems disponibles en inventario'}, status=400)
                messages.error(request, 'No hay módems disponibles en inventario')
                return redirect('realizar_instalacion', instalacion_id=instalacion.id)
        
        # Verificar conectores en BD (sumando buenos y malos)
        conectores_totales_necesarios = conectores_usados + conectores_malos_usados
        inv_conector_bd = InventarioCuadrilla.objects.filter(cuadrilla=cuadrilla, material__nombre="Conector").first()
        if not inv_conector_bd or inv_conector_bd.cantidad < conectores_totales_necesarios:
            if is_ajax:
                return JsonResponse({'error': f'Stock insuficiente de conectores. Necesitas {conectores_totales_necesarios}. Disponible: {inv_conector_bd.cantidad if inv_conector_bd else 0}'}, status=400)
            messages.error(request, f'Stock insuficiente de conectores. Necesitas {conectores_totales_necesarios}. Disponible: {inv_conector_bd.cantidad if inv_conector_bd else 0}')
            return redirect('realizar_instalacion', instalacion_id=instalacion.id)
        
        inv_fibra_bd = InventarioCuadrilla.objects.filter(cuadrilla=cuadrilla, material__nombre="Fibra Optica (metros)").first()
        if not inv_fibra_bd or inv_fibra_bd.cantidad < metros_usados:
            if is_ajax:
                return JsonResponse({'error': f'Stock insuficiente de fibra. Disponible: {inv_fibra_bd.cantidad if inv_fibra_bd else 0}'}, status=400)
            messages.error(request, f'Stock insuficiente de fibra. Disponible: {inv_fibra_bd.cantidad if inv_fibra_bd else 0}')
            return redirect('realizar_instalacion', instalacion_id=instalacion.id)
        
        inv_patch_bd = InventarioCuadrilla.objects.filter(cuadrilla=cuadrilla, material__nombre="Patch Cord").first()
        if not inv_patch_bd or inv_patch_bd.cantidad < patch_usados:
            if is_ajax:
                return JsonResponse({'error': f'Stock insuficiente de patch cord. Disponible: {inv_patch_bd.cantidad if inv_patch_bd else 0}'}, status=400)
            messages.error(request, f'Stock insuficiente de patch cord. Disponible: {inv_patch_bd.cantidad if inv_patch_bd else 0}')
            return redirect('realizar_instalacion', instalacion_id=instalacion.id)
        
        inv_tirro_bd = InventarioCuadrilla.objects.filter(cuadrilla=cuadrilla, material__nombre="Tirros").first()
        if not inv_tirro_bd or inv_tirro_bd.cantidad < tirros_usados:
            if is_ajax:
                return JsonResponse({'error': f'Stock insuficiente de tirros. Disponible: {inv_tirro_bd.cantidad if inv_tirro_bd else 0}'}, status=400)
            messages.error(request, f'Stock insuficiente de tirros. Disponible: {inv_tirro_bd.cantidad if inv_tirro_bd else 0}')
            return redirect('realizar_instalacion', instalacion_id=instalacion.id)
        
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
                
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                filename = f'pagos/instalaciones/instalacion_{instalacion.id}_{timestamp}_{foto.name}'
                saved_path = default_storage.save(filename, foto)
                fotos_urls.append(default_storage.url(saved_path))
            
            fotos_actuales = instalacion.fotos or []
            fotos_actuales.extend(fotos_urls)
            instalacion.fotos = fotos_actuales
            
            instalacion.save()
            
            # ========== GUARDAR INSTALADORES DE LA CUADRILLA ==========
            usuarios_instaladores = [perfil.usuario for perfil in cuadrilla.instaladores.all()]
            if usuarios_instaladores:
                instalacion.instaladores.set(usuarios_instaladores)
            else:
                instalacion.instaladores.add(request.user)
            
            # ========== RESTAR MATERIALES DEL INVENTARIO ==========
            from django.db import transaction
            
            with transaction.atomic():
                # Restar módem
                if modelo_modem_id and modelo_modem_id != '':
                    material_modem, _ = Material.objects.get_or_create(nombre="Modem")
                    inv_cuadrilla_modem, _ = InventarioCuadrilla.objects.get_or_create(
                        cuadrilla=cuadrilla,
                        material=material_modem
                    )
                    if inv_cuadrilla_modem.cantidad >= 1:
                        inv_cuadrilla_modem.cantidad -= 1
                        inv_cuadrilla_modem.save()
                        
                        MovimientoInventario.objects.create(
                            material=material_modem,
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_INSTALACION,
                            cantidad=-1,
                            cuadrilla=cuadrilla,
                            instalacion=instalacion,
                            realizado_por=request.user,
                            observacion=f"Instalación #{instalacion.id} - Módem usado"
                        )
                
                # Restar conectores BUENOS
                if conectores_usados > 0:
                    material_conector, _ = Material.objects.get_or_create(nombre="Conector")
                    inv_cuadrilla, _ = InventarioCuadrilla.objects.get_or_create(
                        cuadrilla=cuadrilla,
                        material=material_conector
                    )
                    if inv_cuadrilla.cantidad >= conectores_usados:
                        inv_cuadrilla.cantidad -= conectores_usados
                        inv_cuadrilla.save()
                        
                        MovimientoInventario.objects.create(
                            material=material_conector,
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_INSTALACION,
                            cantidad=-conectores_usados,
                            cuadrilla=cuadrilla,
                            instalacion=instalacion,
                            realizado_por=request.user,
                            observacion=f"Instalación #{instalacion.id} - {conectores_usados} conectores BUENOS usados"
                        )
                
                # Restar conectores MALOS
                if conectores_malos_usados > 0:
                    material_conector, _ = Material.objects.get_or_create(nombre="Conector")
                    inv_cuadrilla, _ = InventarioCuadrilla.objects.get_or_create(
                        cuadrilla=cuadrilla,
                        material=material_conector
                    )
                    if inv_cuadrilla.cantidad >= conectores_malos_usados:
                        inv_cuadrilla.cantidad -= conectores_malos_usados
                        inv_cuadrilla.save()
                        
                        MovimientoInventario.objects.create(
                            material=material_conector,
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_INSTALACION,
                            cantidad=-conectores_malos_usados,
                            cuadrilla=cuadrilla,
                            instalacion=instalacion,
                            realizado_por=request.user,
                            observacion=f"Instalación #{instalacion.id} - {conectores_malos_usados} conectores MALOS usados"
                        )
                
                # Restar rosetas
                if rosetas_usadas > 0:
                    material_roseta, _ = Material.objects.get_or_create(nombre="Roseta")
                    inv_cuadrilla, _ = InventarioCuadrilla.objects.get_or_create(
                        cuadrilla=cuadrilla,
                        material=material_roseta
                    )
                    if inv_cuadrilla.cantidad >= rosetas_usadas:
                        inv_cuadrilla.cantidad -= rosetas_usadas
                        inv_cuadrilla.save()
                        
                        MovimientoInventario.objects.create(
                            material=material_roseta,
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_INSTALACION,
                            cantidad=-rosetas_usadas,
                            cuadrilla=cuadrilla,
                            instalacion=instalacion,
                            realizado_por=request.user,
                            observacion=f"Instalación #{instalacion.id} - {rosetas_usadas} rosetas usadas"
                        )
                
                # Restar patch cord
                if patch_usados > 0:
                    material_patch, _ = Material.objects.get_or_create(nombre="Patch Cord")
                    inv_cuadrilla, _ = InventarioCuadrilla.objects.get_or_create(
                        cuadrilla=cuadrilla,
                        material=material_patch
                    )
                    if inv_cuadrilla.cantidad >= patch_usados:
                        inv_cuadrilla.cantidad -= patch_usados
                        inv_cuadrilla.save()
                        
                        MovimientoInventario.objects.create(
                            material=material_patch,
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_INSTALACION,
                            cantidad=-patch_usados,
                            cuadrilla=cuadrilla,
                            instalacion=instalacion,
                            realizado_por=request.user,
                            observacion=f"Instalación #{instalacion.id} - {patch_usados} patch cord usados"
                        )
                
                # Restar tensores
                if tensores_usados > 0:
                    material_tensor, _ = Material.objects.get_or_create(nombre="Tensor")
                    inv_cuadrilla, _ = InventarioCuadrilla.objects.get_or_create(
                        cuadrilla=cuadrilla,
                        material=material_tensor
                    )
                    if inv_cuadrilla.cantidad >= tensores_usados:
                        inv_cuadrilla.cantidad -= tensores_usados
                        inv_cuadrilla.save()
                        
                        MovimientoInventario.objects.create(
                            material=material_tensor,
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_INSTALACION,
                            cantidad=-tensores_usados,
                            cuadrilla=cuadrilla,
                            instalacion=instalacion,
                            realizado_por=request.user,
                            observacion=f"Instalación #{instalacion.id} - {tensores_usados} tensores usados"
                        )
                
                # Restar tirros
                if tirros_usados > 0:
                    material_tirro, _ = Material.objects.get_or_create(nombre="Tirros")
                    inv_cuadrilla, _ = InventarioCuadrilla.objects.get_or_create(
                        cuadrilla=cuadrilla,
                        material=material_tirro
                    )
                    if inv_cuadrilla.cantidad >= tirros_usados:
                        inv_cuadrilla.cantidad -= tirros_usados
                        inv_cuadrilla.save()
                        
                        MovimientoInventario.objects.create(
                            material=material_tirro,
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_INSTALACION,
                            cantidad=-tirros_usados,
                            cuadrilla=cuadrilla,
                            instalacion=instalacion,
                            realizado_por=request.user,
                            observacion=f"Instalación #{instalacion.id} - {tirros_usados} tirros usados"
                        )
                
                # Restar fibra
                if metros_usados > 0:
                    material_fibra, _ = Material.objects.get_or_create(nombre="Fibra Optica (metros)")
                    inv_cuadrilla, _ = InventarioCuadrilla.objects.get_or_create(
                        cuadrilla=cuadrilla,
                        material=material_fibra
                    )
                    if inv_cuadrilla.cantidad >= metros_usados:
                        inv_cuadrilla.cantidad -= metros_usados
                        inv_cuadrilla.save()
                        
                        MovimientoInventario.objects.create(
                            material=material_fibra,
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_INSTALACION,
                            cantidad=-metros_usados,
                            cuadrilla=cuadrilla,
                            instalacion=instalacion,
                            realizado_por=request.user,
                            observacion=f"Instalación #{instalacion.id} - {metros_usados} metros de fibra usados"
                        )
            
            # Marcar como completada
            instalacion.completada = True
            instalacion.fecha_instalacion = timezone.now()
            instalacion.save()
            
            # ========== ACTUALIZAR ESTADO DEL CONTRATO ==========
            contrato = instalacion.asignacion.contrato
            if contrato:
                contrato.estado = ContratoCliente.EstadoContrato.COMPLETADO
                contrato.save()
            
            # ========== ACTUALIZAR ESTADO DE LA VENTA DIRECTA ==========
            venta_directa = instalacion.asignacion.venta_directa
            if venta_directa:
                venta_directa.estado = VentaDirecta.EstadoVenta.COMPLETADO
                venta_directa.save()
            
            # ========== ACTUALIZAR ESTADO DE LA CUADRILLA ==========
            instalaciones_pendientes = AsignacionContrato.objects.filter(
                cuadrilla=cuadrilla,
                activo=True
            ).exclude(
                instalacion__completada=True
            ).count()
            
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
            if is_ajax:
                errors = {}
                for field, error_list in form.errors.items():
                    errors[field] = error_list[0] if error_list else ''
                return JsonResponse({'error': errors}, status=400)
            
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Error en {field}: {error}')
    
    # ========== GET: Mostrar formulario ==========
    form = InstalacionForm(instance=instalacion)
    modelos_modem = ModeloModem.objects.filter(activo=True).order_by('nombre')
    fotos_existentes = json.dumps(instalacion.fotos or [])
    instaladores_seleccionados = list(instalacion.instaladores.values_list('id', flat=True))
    
    context = {
        'form': form,
        'instalacion': instalacion,
        'modelos_modem': modelos_modem,
        'ubicacion_cuadrilla': ubicacion_cuadrilla,
        'fotos_existentes': fotos_existentes,
        'es_admin': es_admin,
        'instaladores_disponibles': instaladores_de_cuadrilla,
        'instaladores_seleccionados': instaladores_seleccionados,
        'inventario_cuadrilla': inventario_cuadrilla,
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
        
        
        # ========== OBTENER DIRECCIÓN ==========
        direccion = "No registrada"
        if instalacion.asignacion.contrato:
            direccion = instalacion.asignacion.contrato.direccion_detallada or "No registrada"
        elif instalacion.asignacion.venta_directa:
            direccion = getattr(instalacion.asignacion.venta_directa, 'direccion', None) or "No registrada"
        
        # ========== OBTENER TELÉFONO DEL CLIENTE ==========
        telefono_cliente = "No disponible"
        if instalacion.asignacion.contrato:
            telefono_cliente = instalacion.asignacion.contrato.telefono_principal or "No disponible"
        elif instalacion.asignacion.venta_directa:
            telefono_cliente = instalacion.asignacion.venta_directa.telefono or "No disponible"
        
        # ========== OBTENER INFORMACIÓN DEL VENDEDOR/TORRE ==========
        vendedor_nombre = "No disponible"
        vendedor_usuario = "-"
        vendedor_telefono = "No registrado"
        vendedor_email = "-"
        
        if instalacion.asignacion.contrato:
            # Es un contrato de vendedor
            creador = instalacion.asignacion.contrato.creado_por
            if creador:
                vendedor_nombre = creador.get_full_name() or creador.username
                vendedor_usuario = creador.username
                vendedor_email = creador.email or "-"
                try:
                    perfil_vendedor = creador.perfil
                    vendedor_telefono = perfil_vendedor.telefono or "No registrado"
                except:
                    vendedor_telefono = "No registrado"
        elif instalacion.asignacion.venta_directa:
            # Es una venta directa (Torre de Control)
            creador = instalacion.asignacion.venta_directa.creado_por
            if creador:
                vendedor_nombre = creador.get_full_name() or "Torre de Control"
                vendedor_usuario = creador.username or "torre_control"
                vendedor_email = creador.email or "torre@vtconexiones.com"
                try:
                    perfil_vendedor = creador.perfil
                    vendedor_telefono = perfil_vendedor.telefono or "0412-1234567"
                except:
                    vendedor_telefono = "0412-1234567"
        
        # Construir datos de la instalación
        datos = {
            'id': instalacion.id,
            'orden_servicio': instalacion.orden_servicio,
            'nro_orden': instalacion.nro_orden,
            'nombre_cliente': instalacion.nombre_cliente,
            'cedula_cliente': instalacion.cedula_cliente,
            'telefono_cliente': telefono_cliente,
            'direccion': direccion,
            'plan': instalacion.plan,
            'cuadrilla': instalacion.asignacion.cuadrilla.nombre if instalacion.asignacion.cuadrilla else "N/A",
            'estado': 'Completada' if instalacion.completada else 'Pendiente',
            'fecha_instalacion': instalacion.fecha_instalacion.strftime('%d/%m/%Y %H:%M') if instalacion.fecha_instalacion else 'No registrada',
            'fecha_asignacion': instalacion.asignacion.fecha_asignacion.strftime('%d/%m/%Y %H:%M'),
            
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
            'tipo': 'contrato' if instalacion.asignacion.contrato else 'venta_directa',
            'creado_por': instalacion.creado_por_nombre,
            'customer_id': instalacion.customer_id,
            'atr': instalacion.atr,
            
            # Datos del vendedor/torre
            'vendedor_nombre': vendedor_nombre,
            'vendedor_usuario': vendedor_usuario,
            'vendedor_telefono': vendedor_telefono,
            'vendedor_email': vendedor_email,
            'trabajo_interno': instalacion.asignacion.trabajo_interno or False,
        }
        
        return JsonResponse({'success': True, 'data': datos})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

