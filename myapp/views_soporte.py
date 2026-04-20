from django.utils import timezone 
import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required,user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

from myapp.forms import InstalacionForm, SoporteEditarForm, SoporteForm
from .models import *
from django.db.models import Q, Prefetch
from django.core.files.storage import default_storage
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt

from myapp.models import Soporte, Instalacion, Cuadrilla, User, ContratoCliente, VentaDirecta, ModeloModem
from myapp.forms import SoporteForm


def es_instalador_o_admin(user):
    """Verifica si el usuario es instalador o administrador"""
    return user.is_superuser or user.groups.filter(name='Administrador').exists() or user.groups.filter(name='Instalador').exists()


@login_required
@user_passes_test(es_instalador_o_admin)
def crear_soporte_unificado(request):
    """Vista unificada para crear soporte - todo en una sola página"""
    
    tipos_soporte = Soporte.TipoSoporte.choices
    instalacion_encontrada = None
    cliente_data = None
    form = None
    mostrar_formulario = False
    error_busqueda = None
    
    if request.method == 'POST':
        # Verificar si es búsqueda o guardado
        if 'buscar_cliente' in request.POST:
            # PASO 1: Búsqueda del cliente
            tipo_soporte = request.POST.get('tipo_soporte')
            busqueda = request.POST.get('busqueda', '').strip()
            
            if not tipo_soporte:
                error_busqueda = 'Debe seleccionar un tipo de soporte'
            elif not busqueda:
                error_busqueda = 'Debe ingresar Customer ID o Número de Orden (ODS)'
            else:
                # Buscar por customer_id o nro_orden (ODS)
                contrato = ContratoCliente.objects.filter(
                    Q(customer_id__iexact=busqueda)
                ).select_related('cliente_potencial', 'plan_contratado').first()
                
                if not contrato:
                    venta = VentaDirecta.objects.filter(
                        Q(customer_id__iexact=busqueda) |
                        Q(nro_orden__iexact=busqueda)
                    ).select_related('plan').first()
                    
                    if venta:
                        cliente_data = {
                            'id': venta.id,
                            'tipo_cliente': 'venta',
                            'nombre': venta.nombre_completo,
                            'cedula': venta.cedula,
                            'telefono': venta.telefono,
                            'direccion': venta.direccion if hasattr(venta, 'direccion') else 'No registrada',
                            'customer_id': venta.customer_id,
                            'plan': venta.plan.nombre,
                            'nro_orden': venta.nro_orden,
                            'atr': '*VTC Conexiones',
                        }
                        instalacion_encontrada = Instalacion.objects.filter(
                            asignacion__venta_directa=venta,
                            completada=True
                        ).select_related('asignacion', 'modelo_modem').first()
                else:
                    cliente_data = {
                        'id': contrato.cliente_potencial.id,
                        'tipo_cliente': 'contrato',
                        'nombre': contrato.cliente_potencial.nombre_completo,
                        'cedula': contrato.cliente_potencial.cedula,
                        'telefono': contrato.cliente_potencial.telefono,
                        'direccion': contrato.direccion_detallada,
                        'customer_id': contrato.customer_id,
                        'plan': contrato.plan_contratado.nombre,
                        'atr': contrato.atr,
                        'ods': contrato.ods,
                    }
                    instalacion_encontrada = Instalacion.objects.filter(
                        asignacion__contrato=contrato,
                        completada=True
                    ).select_related('asignacion', 'modelo_modem').first()
                
                if not cliente_data:
                    error_busqueda = f'No se encontró ningún cliente con Customer ID o Número de Orden: {busqueda}'
                elif not instalacion_encontrada:
                    error_busqueda = 'El cliente no tiene una instalación completada para realizar soporte'
                else:
                    soporte_existente = Soporte.objects.filter(
                        instalacion=instalacion_encontrada,
                        tipo=tipo_soporte,
                        estado__in=['PENDIENTE', 'EN_PROCESO']
                    ).first()
                    
                    if soporte_existente:
                        error_busqueda = f'Ya existe un soporte de {dict(tipos_soporte).get(tipo_soporte)} para este cliente en estado {soporte_existente.get_estado_display()}'
                    else:
                        mostrar_formulario = True
                        form = SoporteForm(initial={
                            'tipo': tipo_soporte,
                            'instalacion': instalacion_encontrada.id,
                        })
        
        elif 'guardar_soporte' in request.POST:
            # PASO 2: Guardar el soporte
            instalacion_id = request.POST.get('instalacion_id')
            tipo_soporte = request.POST.get('tipo_soporte')
            
            if not instalacion_id:
                messages.error(request, 'Error: No se encontró la instalación')
                return redirect('crear_soporte_unificado')
            
            instalacion_encontrada = get_object_or_404(Instalacion, id=instalacion_id)
            cuadrilla = instalacion_encontrada.asignacion.cuadrilla
            
            # ========== OBTENER INVENTARIO DE LA CUADRILLA ==========
            inventario_cuadrilla = {
                "Modem": 0,
                "Conector": 0,
                "Roseta": 0,
                "Patch Cord": 0,
                "Tensor": 0,
                "Fibra Optica (metros)": 0
            }
            
            try:
                materiales_disponibles = InventarioCuadrilla.objects.filter(cuadrilla=cuadrilla).select_related('material')
                for item in materiales_disponibles:
                    inventario_cuadrilla[item.material.nombre] = item.cantidad
            except:
                pass
            
            # ========== OBTENER VALORES DEL POST ==========
            inicio_fibra = int(request.POST.get('inicio_fibra', 0) or 0)
            final_fibra = int(request.POST.get('final_fibra', 0) or 0)
            metros_usados = abs(inicio_fibra - final_fibra) if inicio_fibra > 0 or final_fibra > 0 else 0
            
            conectores_usados = int(request.POST.get('conectores', 0) or 0)
            rosetas_usadas = int(request.POST.get('rosetas', 0) or 0)
            patch_usados = int(request.POST.get('patch_cord', 0) or 0)
            tensores_usados = int(request.POST.get('tensores', 0) or 0)
            modelo_modem_id = request.POST.get('modelo_modem')
            
            # ========== VALIDAR STOCK ANTES DE GUARDAR ==========
            errores_stock = []
            
            # Validar módem (solo si se seleccionó un modelo)
            if modelo_modem_id and modelo_modem_id != '':
                if inventario_cuadrilla.get("Modem", 0) < 1:
                    errores_stock.append("No hay módems disponibles en el inventario de la cuadrilla.")
            
            # Validar conectores (solo si se usaron)
            if conectores_usados > 0 and conectores_usados > inventario_cuadrilla.get("Conector", 0):
                errores_stock.append(f"Stock insuficiente de conectores. Disponible: {inventario_cuadrilla.get('Conector', 0)}")
            
            # Validar rosetas (solo si se usaron)
            if rosetas_usadas > 0 and rosetas_usadas > inventario_cuadrilla.get("Roseta", 0):
                errores_stock.append(f"Stock insuficiente de rosetas. Disponible: {inventario_cuadrilla.get('Roseta', 0)}")
            
            # Validar patch cord (solo si se usaron)
            if patch_usados > 0 and patch_usados > inventario_cuadrilla.get("Patch Cord", 0):
                errores_stock.append(f"Stock insuficiente de patch cord. Disponible: {inventario_cuadrilla.get('Patch Cord', 0)}")
            
            # Validar tensores (solo si se usaron)
            if tensores_usados > 0 and tensores_usados > inventario_cuadrilla.get("Tensor", 0):
                errores_stock.append(f"Stock insuficiente de tensores. Disponible: {inventario_cuadrilla.get('Tensor', 0)}")
            
            # Validar fibra (solo si se usaron metros)
            if metros_usados > 0 and metros_usados > inventario_cuadrilla.get("Fibra Optica (metros)", 0):
                errores_stock.append(f"Stock insuficiente de fibra óptica. Metros disponibles: {inventario_cuadrilla.get('Fibra Optica (metros)', 0)}")
            
            # Si hay errores de stock
            if errores_stock:
                for error in errores_stock:
                    messages.error(request, f'❌ {error}')
                # Recargar datos para mostrar el formulario nuevamente
                cliente_data = {
                    'nombre': instalacion_encontrada.nombre_cliente,
                    'cedula': instalacion_encontrada.cedula_cliente,
                    'direccion': instalacion_encontrada.direccion,
                    'customer_id': instalacion_encontrada.customer_id,
                    'plan': instalacion_encontrada.plan,
                    'atr': instalacion_encontrada.atr,
                }
                mostrar_formulario = True
                form = SoporteForm(initial={
                    'tipo': tipo_soporte,
                    'instalacion': instalacion_encontrada.id,
                })
                form.data = request.POST
                context = {
                    'tipos_soporte': tipos_soporte,
                    'cliente': cliente_data,
                    'instalacion': instalacion_encontrada,
                    'form': form,
                    'mostrar_formulario': mostrar_formulario,
                    'busqueda_realizada': True,
                    'error_busqueda': None,
                    'modelos_modem': ModeloModem.objects.filter(activo=True),
                }
                return render(request, 'Instaladores/crear_soporte.html', context)
            
            # Crear el soporte manualmente
            try:
                from django.db import transaction
                
                with transaction.atomic():
                    soporte = Soporte()
                    soporte.instalacion = instalacion_encontrada
                    soporte.tipo = tipo_soporte
                    soporte.creado_por = request.user
                    soporte.estado = 'COMPLETADO'  # Se completa directamente
                    
                    # Asignar fecha y hora
                    fecha_hora = request.POST.get('fecha_hora_servicio')
                    if fecha_hora:
                        import datetime
                        soporte.fecha_hora_servicio = datetime.datetime.strptime(fecha_hora, '%Y-%m-%dT%H:%M')
                    else:
                        soporte.fecha_hora_servicio = timezone.now()
                    
                    # Asignar falla y solución
                    soporte.falla_encontrada = request.POST.get('falla_encontrada', '')
                    soporte.solucion = request.POST.get('solucion', '')
                    
                    # Asignar módem
                    if modelo_modem_id and modelo_modem_id != '':
                        soporte.modelo_modem_id = modelo_modem_id
                    soporte.sn_modem = request.POST.get('sn_modem', '')
                    soporte.mac_modem = request.POST.get('mac_modem', '')
                    
                    # Asignar materiales
                    soporte.inicio_fibra = request.POST.get('inicio_fibra') or None
                    soporte.final_fibra = request.POST.get('final_fibra') or None
                    soporte.conectores = int(request.POST.get('conectores', 0) or 0)
                    soporte.rosetas = int(request.POST.get('rosetas', 0) or 0)
                    soporte.patch_cord = int(request.POST.get('patch_cord', 0) or 0)
                    soporte.tensores = int(request.POST.get('tensores', 0) or 0)
                    soporte.conectores_malos = int(request.POST.get('conectores_malos', 0) or 0)
                    
                    # Asignar datos NAP
                    soporte.caja_nap_utilizada = request.POST.get('caja_nap_utilizada', '')
                    soporte.puerto_nap_utilizado = request.POST.get('puerto_nap_utilizado', '')
                    
                    # Asignar ubicación
                    soporte.pin_ubicacion_lat = request.POST.get('pin_ubicacion_lat') or None
                    soporte.pin_ubicacion_lng = request.POST.get('pin_ubicacion_lng') or None
                    
                    # Asignar observaciones
                    soporte.observaciones = request.POST.get('observaciones', '')
                    
                    # Asignar cuadrilla actual del usuario
                    try:
                        perfil = request.user.perfil
                        cuadrilla_asignada = Cuadrilla.objects.filter(instaladores=perfil).first()
                        soporte.cuadrilla = cuadrilla_asignada
                    except:
                        pass
                    
                    soporte.save()
                    
                    # ========== GUARDAR TODOS LOS INSTALADORES DE LA CUADRILLA ==========
                    if soporte.cuadrilla:
                        # Obtener todos los usuarios de los perfiles de la cuadrilla
                        for perfil_instalador in soporte.cuadrilla.instaladores.all():
                            soporte.instaladores.add(perfil_instalador.usuario)
                    else:
                        # Si no se encuentra la cuadrilla, al menos guardar al usuario actual
                        soporte.instaladores.add(request.user)
                    
                    # Procesar fotos
                    fotos = request.FILES.getlist('fotos_upload')
                    if fotos:
                        from django.core.files.storage import default_storage
                        import os
                        from django.utils import timezone as tz
                        fotos_urls = []
                        for foto in fotos:
                            extension = os.path.splitext(foto.name)[1].lower()
                            nombre_archivo = f"soporte_{soporte.id}_{int(tz.now().timestamp())}{extension}"
                            ruta = os.path.join('soportes', nombre_archivo)
                            saved_path = default_storage.save(ruta, foto)
                            fotos_urls.append(default_storage.url(saved_path))
                        
                        soporte.fotos = fotos_urls
                        soporte.save()
                    
                    # ========== RESTAR MATERIALES DEL INVENTARIO ==========
                    # Restar módem (solo si se seleccionó un modelo)
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
                                tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                                cantidad=-1,
                                cuadrilla=cuadrilla,
                                soporte=soporte,
                                realizado_por=request.user,
                                observacion=f"Soporte #{soporte.id} - Módem usado"
                            )
                    
                    # Restar conectores (solo si se usaron)
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
                                tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                                cantidad=-conectores_usados,
                                cuadrilla=cuadrilla,
                                soporte=soporte,
                                realizado_por=request.user,
                                observacion=f"Soporte #{soporte.id} - {conectores_usados} conectores usados"
                            )
                    
                    # Restar rosetas (solo si se usaron)
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
                                tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                                cantidad=-rosetas_usadas,
                                cuadrilla=cuadrilla,
                                soporte=soporte,
                                realizado_por=request.user,
                                observacion=f"Soporte #{soporte.id} - {rosetas_usadas} rosetas usadas"
                            )
                    
                    # Restar patch cord (solo si se usaron)
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
                                tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                                cantidad=-patch_usados,
                                cuadrilla=cuadrilla,
                                soporte=soporte,
                                realizado_por=request.user,
                                observacion=f"Soporte #{soporte.id} - {patch_usados} patch cord usados"
                            )
                    
                    # Restar tensores (solo si se usaron)
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
                                tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                                cantidad=-tensores_usados,
                                cuadrilla=cuadrilla,
                                soporte=soporte,
                                realizado_por=request.user,
                                observacion=f"Soporte #{soporte.id} - {tensores_usados} tensores usados"
                            )
                    
                    # Restar fibra (solo si se usaron metros)
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
                                tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                                cantidad=-metros_usados,
                                cuadrilla=cuadrilla,
                                soporte=soporte,
                                realizado_por=request.user,
                                observacion=f"Soporte #{soporte.id} - {metros_usados} metros de fibra usados"
                            )
                
                messages.success(request, f'Soporte de {dict(tipos_soporte).get(tipo_soporte)} creado exitosamente')
                return redirect('lista_soportes')
                
            except Exception as e:
                messages.error(request, f'Error al crear el soporte: {str(e)}')
                # Recargar datos para mostrar el formulario nuevamente
                cliente_data = {
                    'nombre': instalacion_encontrada.nombre_cliente,
                    'cedula': instalacion_encontrada.cedula_cliente,
                    'direccion': instalacion_encontrada.direccion,
                    'customer_id': instalacion_encontrada.customer_id,
                    'plan': instalacion_encontrada.plan,
                    'atr': instalacion_encontrada.atr,
                }
                mostrar_formulario = True
                form = SoporteForm(initial={
                    'tipo': tipo_soporte,
                    'instalacion': instalacion_encontrada.id,
                })
                form.data = request.POST
                context = {
                    'tipos_soporte': tipos_soporte,
                    'cliente': cliente_data,
                    'instalacion': instalacion_encontrada,
                    'form': form,
                    'mostrar_formulario': mostrar_formulario,
                    'busqueda_realizada': True,
                    'error_busqueda': None,
                    'modelos_modem': ModeloModem.objects.filter(activo=True),
                }
                return render(request, 'Instaladores/crear_soporte.html', context)
    
    # GET request
    context = {
        'tipos_soporte': tipos_soporte,
        'cliente': cliente_data,
        'instalacion': instalacion_encontrada,
        'form': form,
        'mostrar_formulario': mostrar_formulario,
        'busqueda_realizada': False,
        'error_busqueda': error_busqueda,
        'modelos_modem': ModeloModem.objects.filter(activo=True),
    }
    return render(request, 'Instaladores/crear_soporte.html', context)


@login_required
@user_passes_test(es_instalador_o_admin)
def editar_soporte(request, soporte_id):
    """Editar un soporte existente"""
    
    soporte = get_object_or_404(Soporte, id=soporte_id)
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    # Verificar permisos
    if not es_admin and request.user not in soporte.instaladores.all():
        messages.error(request, 'No tienes permiso para editar este soporte')
        return redirect('lista_soportes')
    
    # Obtener modelos de módem activos
    modelos_modem = ModeloModem.objects.filter(activo=True)
    
    if request.method == 'POST':
        # Usar SoporteEditForm (excluye estado, instaladores, fotos)
        form = SoporteEditarForm(request.POST, request.FILES, instance=soporte)
        
        if form.is_valid():
            soporte = form.save()
            
            # Procesar eliminación de fotos existentes
            fotos_eliminar = request.POST.get('fotos_eliminar', '')
            if fotos_eliminar:
                import json
                fotos_a_eliminar = json.loads(fotos_eliminar)
                from django.core.files.storage import default_storage
                fotos_actuales = soporte.fotos or []
                for foto_url in fotos_a_eliminar:
                    if foto_url in fotos_actuales:
                        fotos_actuales.remove(foto_url)
                        if '/media/' in foto_url:
                            ruta = foto_url.split('/media/')[-1]
                            if default_storage.exists(ruta):
                                default_storage.delete(ruta)
                soporte.fotos = fotos_actuales
                soporte.save()
            
            # Procesar NUEVAS fotos (solo se agregan, no se reemplazan)
            fotos = request.FILES.getlist('fotos_upload')
            if fotos:
                from django.core.files.storage import default_storage
                import os
                from django.utils import timezone as tz
                fotos_urls = soporte.fotos or []
                for foto in fotos:
                    extension = os.path.splitext(foto.name)[1].lower()
                    nombre_archivo = f"soporte_{soporte.id}_{int(tz.now().timestamp())}{extension}"
                    ruta = os.path.join('soportes', nombre_archivo)
                    saved_path = default_storage.save(ruta, foto)
                    fotos_urls.append(default_storage.url(saved_path))
                soporte.fotos = fotos_urls
                soporte.save()
            
            messages.success(request, 'Soporte actualizado exitosamente')
            return redirect('lista_soportes')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Error en {field}: {error}')
    else:
        form = SoporteEditarForm(instance=soporte)
    
    context = {
        'form': form,
        'soporte': soporte,
        'modelos_modem': modelos_modem,
    }
    return render(request, 'Instaladores/editar_soporte.html', context)

@login_required
def eliminar_foto_soporte(request, soporte_id):
    """Eliminar una foto específica del soporte"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    soporte = get_object_or_404(Soporte, id=soporte_id)
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    if not es_admin and request.user not in soporte.instaladores.all():
        return JsonResponse({'error': 'No tienes permiso'}, status=403)
    
    try:
        import json
        data = json.loads(request.body)
        foto_url = data.get('foto_url')
        
        if foto_url and foto_url in soporte.fotos:
            soporte.fotos.remove(foto_url)
            soporte.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'Foto no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    
    
def es_instalador_o_admin(user):
    """Verifica si el usuario es instalador o administrador"""
    return user.is_superuser or user.groups.filter(name='Administrador').exists() or user.groups.filter(name='Instalador').exists()


@login_required
@user_passes_test(es_instalador_o_admin)
def lista_soportes(request):
    """Lista todos los soportes con filtros y búsqueda"""
    
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_instalador = request.user.groups.filter(name='Instalador').exists()
    
    # Base query - todos los soportes
    soportes = Soporte.objects.all().select_related(
        'instalacion', 
        'instalacion__asignacion__contrato__cliente_potencial',
        'instalacion__asignacion__venta_directa',
        'cuadrilla',
        'modelo_modem'  # ← Agregado para optimizar consulta del módem
    ).prefetch_related('instaladores')
    
    # Si no es admin, solo ve los soportes donde participó o de su cuadrilla
    if not es_admin:
        # Obtener cuadrilla del usuario
        try:
            perfil = request.user.perfil
            cuadrilla = Cuadrilla.objects.filter(instaladores=perfil).first()
            if cuadrilla:
                soportes = soportes.filter(
                    Q(instaladores=request.user) | Q(cuadrilla=cuadrilla)
                ).distinct()
            else:
                soportes = soportes.filter(instaladores=request.user)
        except:
            soportes = soportes.filter(instaladores=request.user)
    
    # ===== FILTROS =====
    # Filtro por búsqueda (cliente, cédula)
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        soportes = soportes.filter(
            Q(instalacion__asignacion__contrato__cliente_potencial__nombre__icontains=busqueda) |
            Q(instalacion__asignacion__contrato__cliente_potencial__apellido__icontains=busqueda) |
            Q(instalacion__asignacion__contrato__cliente_potencial__cedula__icontains=busqueda) |
            Q(instalacion__asignacion__venta_directa__nombre__icontains=busqueda) |
            Q(instalacion__asignacion__venta_directa__apellido__icontains=busqueda) |
            Q(instalacion__asignacion__venta_directa__cedula__icontains=busqueda)
        )
    
    # Filtro por tipo de soporte
    tipo = request.GET.get('tipo', '')
    if tipo:
        soportes = soportes.filter(tipo=tipo)
    
    # Filtro por estado
    estado = request.GET.get('estado', '')
    if estado:
        soportes = soportes.filter(estado=estado)
    
    # Filtro por fecha
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    if fecha_desde:
        soportes = soportes.filter(fecha_hora_servicio__date__gte=fecha_desde)
    if fecha_hasta:
        soportes = soportes.filter(fecha_hora_servicio__date__lte=fecha_hasta)
    
    # Filtro por instalador (solo admin)
    instalador_id = request.GET.get('instalador', '')
    if instalador_id and es_admin:
        soportes = soportes.filter(instaladores__id=instalador_id)
    
    # ===== ESTADÍSTICAS =====
    total_soportes = soportes.count()
    pendientes = soportes.filter(estado='PENDIENTE').count()
    en_proceso = soportes.filter(estado='EN_PROCESO').count()
    completados = soportes.filter(estado='COMPLETADO').count()
    incompletos = soportes.filter(estado='INCOMPLETO').count()
    cancelados = soportes.filter(estado='CANCELADO').count()
    
    # Estadísticas por tipo
    mudanzas = soportes.filter(tipo='MUDANZA').count()
    retiros = soportes.filter(tipo='RETIRO').count()
    recableados = soportes.filter(tipo='RECABLEADO').count()
    
    # Soportes del día de hoy
    hoy = timezone.now().date()
    soportes_hoy = soportes.filter(fecha_hora_servicio__date=hoy).count()
    
    # Soportes de la semana
    semana_pasada = hoy - timedelta(days=7)
    soportes_semana = soportes.filter(fecha_hora_servicio__date__gte=semana_pasada).count()
    
    # ===== LISTA DE INSTALADORES PARA EL FILTRO (solo admin) =====
    instaladores = []
    if es_admin:
        instaladores = User.objects.filter(
            groups__name='Instalador'
        ).distinct().order_by('first_name', 'username')
    
    # ===== PAGINACIÓN =====
    paginator = Paginator(soportes, 15)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    
    context = {
        'page_obj': page_obj,
        'total_soportes': total_soportes,
        'pendientes': pendientes,
        'en_proceso': en_proceso,
        'completados': completados,
        'incompletos': incompletos,
        'cancelados': cancelados,
        'mudanzas': mudanzas,
        'retiros': retiros,
        'recableados': recableados,
        'soportes_hoy': soportes_hoy,
        'soportes_semana': soportes_semana,
        'busqueda': busqueda,
        'tipo_seleccionado': tipo,
        'estado_seleccionado': estado,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'instalador_seleccionado': instalador_id,
        'es_admin': es_admin,
        'es_instalador': es_instalador,
        'instaladores': instaladores,
    }
    return render(request, 'Instaladores/lista_soportes.html', context)


@login_required
@user_passes_test(es_instalador_o_admin)
def detalle_soporte(request, soporte_id):
    """Ver detalle completo de un soporte"""
    
    soporte = get_object_or_404(Soporte, id=soporte_id)
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    # Verificar permisos
    if not es_admin and request.user not in soporte.instaladores.all():
        messages.error(request, 'No tienes permiso para ver este soporte')
        return redirect('lista_soportes')
    
    # Convertir materiales a lista para el template
    materiales = []
    if soporte.inicio_fibra or soporte.final_fibra:
        materiales.append({'nombre': 'FIBRA', 'valor': f"{soporte.inicio_fibra or 0} - {soporte.final_fibra or 0} ({soporte.metros_utilizados} mts)"})
    if soporte.conectores:
        materiales.append({'nombre': 'CONECTORES', 'valor': soporte.conectores})
    if soporte.rosetas:
        materiales.append({'nombre': 'ROSETAS', 'valor': soporte.rosetas})
    if soporte.patch_cord:
        materiales.append({'nombre': 'PATCH CORD', 'valor': soporte.patch_cord})
    if soporte.tensores:
        materiales.append({'nombre': 'TENSORES', 'valor': soporte.tensores})
    if soporte.conectores_malos:
        materiales.append({'nombre': 'CONECTORES MALOS', 'valor': soporte.conectores_malos})
    
    context = {
        'soporte': soporte,
        'materiales': materiales,
        'es_admin': es_admin,
    }
    return render(request, 'Instaladores/detalle_soporte.html', context)


from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

@login_required
@user_passes_test(es_instalador_o_admin)
@require_http_methods(["GET"])
def detalle_soporte_json(request, soporte_id):
    """Retorna los detalles de un soporte en formato JSON para el modal"""
    
    soporte = get_object_or_404(Soporte, id=soporte_id)
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    # Verificar permisos
    if not es_admin and request.user not in soporte.instaladores.all():
        return JsonResponse({'error': 'No tienes permiso para ver este soporte'}, status=403)
    
    # Obtener instaladores
    instaladores = [inst.get_full_name() or inst.username for inst in soporte.instaladores.all()]
    
    # Construir respuesta
    data = {
        'id': soporte.id,
        'tipo': soporte.tipo,
        'tipo_display': soporte.get_tipo_display(),
        'estado': soporte.estado,
        'estado_display': soporte.get_estado_display(),
        'fecha_hora_servicio': soporte.fecha_hora_servicio.strftime('%d/%m/%Y %H:%M'),
        'fecha_creacion': soporte.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        'fecha_actualizacion': soporte.fecha_actualizacion.strftime('%d/%m/%Y %H:%M'),
        
        # Información del cliente
        'cliente_nombre': soporte.nombre_cliente,
        'cliente_cedula': soporte.cedula_cliente,
        'direccion': soporte.direccion,
        'customer_id': soporte.customer_id,
        'plan': soporte.plan,
        'atr': soporte.atr,
        
        # Información de la instalación original
        'instalacion_id': soporte.instalacion.id,
        'modelo_modem_original': soporte.instalacion.modelo_modem.nombre if soporte.instalacion.modelo_modem else 'N/A',
        'sn_modem_original': soporte.instalacion.sn_modem or 'N/A',
        
        # Datos del soporte
        'falla_encontrada': soporte.falla_encontrada,
        'solucion': soporte.solucion,
        'observaciones': soporte.observaciones or '',
        
        # Datos del nuevo módem (si aplica)
        'modelo_modem': soporte.modelo_modem.nombre if soporte.modelo_modem else 'No se cambió',
        'sn_modem': soporte.sn_modem or 'No se cambió',
        'mac_modem': soporte.mac_modem or 'No se cambió',
        
        # Materiales
        'inicio_fibra': soporte.inicio_fibra,
        'final_fibra': soporte.final_fibra,
        'metros_utilizados': soporte.metros_utilizados,
        'conectores': soporte.conectores or 0,
        'rosetas': soporte.rosetas or 0,
        'patch_cord': soporte.patch_cord or 0,
        'tensores': soporte.tensores or 0,
        'conectores_malos': soporte.conectores_malos or 0,
        
        # Datos NAP
        'caja_nap_utilizada': soporte.caja_nap_utilizada or 'N/A',
        'puerto_nap_utilizado': soporte.puerto_nap_utilizado or 'N/A',
        
        # Ubicación
        'pin_ubicacion_lat': soporte.pin_ubicacion_lat,
        'pin_ubicacion_lng': soporte.pin_ubicacion_lng,
        'pin_ubicacion_url': f"https://www.google.com/maps?q={soporte.pin_ubicacion_lat},{soporte.pin_ubicacion_lng}" if soporte.pin_ubicacion_lat and soporte.pin_ubicacion_lng else None,
        
        # Fotos
        'fotos': soporte.fotos or [],
        
        # Instaladores
        'instaladores': instaladores,
        
        # Cuadrilla
        'cuadrilla': soporte.cuadrilla.nombre if soporte.cuadrilla else 'No asignada',
        
        # Permisos
        'puede_editar': soporte.estado not in ['COMPLETADO', 'CANCELADO'],
        'es_admin': es_admin,
    }
    
    return JsonResponse(data)    