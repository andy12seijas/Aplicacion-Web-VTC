from email.headerregistry import Group
import json
import os
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from .models import ClientePotencial
from .forms import ClientePotencialForm, ContratoClienteForm
from django.contrib.auth.models import User, Group 
from .decorators import admin_required
from myapp.models import *
from django.views.decorators.csrf import csrf_exempt

# ============================================
# VISTA PARA LISTAR CLIENTES
# ============================================
@login_required
def lista_clientes(request):
    """Lista todos los clientes potenciales con filtros y búsqueda"""
    
    # 👥 DETERMINAR SI ES ADMIN (definir al principio)
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    # Base query - todos los clientes
    clientes = ClientePotencial.objects.all().select_related('creado_por')
    
    # Si no es admin, solo ve sus propios clientes
    if not es_admin:
        clientes = clientes.filter(creado_por=request.user)
    
    # ===== FILTROS =====
    # Filtro por búsqueda (nombre, apellido, cédula, teléfono)
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        clientes = clientes.filter(
            Q(cedula__icontains=busqueda) |
            Q(nombre__icontains=busqueda) |
            Q(apellido__icontains=busqueda) |
            Q(telefono__icontains=busqueda) |
            Q(direccion__icontains=busqueda)
        )
    
    # Filtro por nivel de interés
    interes = request.GET.get('interes', '')
    if interes:
        clientes = clientes.filter(interesado=interes)
    
    # Filtro por posee internet
    internet = request.GET.get('internet', '')
    if internet == 'si':
        clientes = clientes.filter(posee_internet=True)
    elif internet == 'no':
        clientes = clientes.filter(posee_internet=False)
    
    # FILTRO POR VENDEDOR (solo para administradores)
    vendedor_filtro = request.GET.get('vendedor', '')
    if vendedor_filtro and es_admin:
        clientes = clientes.filter(creado_por__username=vendedor_filtro)
    
    # Filtro por rango de fechas
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    if fecha_desde:
        clientes = clientes.filter(fecha_registro__gte=fecha_desde)
    if fecha_hasta:
        clientes = clientes.filter(fecha_registro__lte=fecha_hasta)
    
    # ===== ESTADÍSTICAS =====
    total_clientes = clientes.count()
    interesados = clientes.filter(interesado='SI').count()
    tal_vez = clientes.filter(interesado='TAL_VEZ').count()
    no_interesados = clientes.filter(interesado='NO').count()
    con_internet = clientes.filter(posee_internet=True).count()
    sin_internet = clientes.filter(posee_internet=False).count()
    
    # Clientes registrados hoy
    hoy = timezone.now().date()
    clientes_hoy = clientes.filter(fecha_registro=hoy).count()
    
    # Clientes de esta semana
    semana_pasada = hoy - timedelta(days=7)
    clientes_semana = clientes.filter(fecha_registro__gte=semana_pasada).count()
    
    # ===== LISTA DE VENDEDORES PARA EL FILTRO (solo para admin) =====
    vendedores = []
    if es_admin:
        # 🔥 CAMBIO AQUÍ: TODOS los usuarios del sistema
        vendedores = User.objects.all().order_by('username')
    
    # ===== PAGINACIÓN =====
    paginator = Paginator(clientes, 5)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    
    context = {
        'page_obj': page_obj,
        'busqueda': busqueda,
        'interes_seleccionado': interes,
        'internet_seleccionado': internet,
        'vendedor_filtro': vendedor_filtro,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        # Estadísticas
        'total_clientes': total_clientes,
        'interesados': interesados,
        'tal_vez': tal_vez,
        'no_interesados': no_interesados,
        'con_internet': con_internet,
        'sin_internet': sin_internet,
        'clientes_hoy': clientes_hoy,
        'clientes_semana': clientes_semana,
        'es_admin': es_admin,
        'vendedores': vendedores,  # ✅ Ahora son TODOS los usuarios
    }
    return render(request, 'Vendedores/lista_clientes.html', context)

@login_required
def crear_cliente(request):
    """Crea un nuevo cliente potencial"""
    
    if request.method == 'POST':
        form = ClientePotencialForm(request.POST, es_creacion=True)
        if form.is_valid():
            cliente = form.save(commit=False)
            # Asignar el usuario actual como creador
            cliente.creado_por = request.user
            cliente.save()
            
             # 2. ACTUALIZAR la ubicación del usuario
            latitud = request.POST.get('latitud')
            longitud = request.POST.get('longitud')
            
            if latitud and longitud:
                # Crear texto asociado para referencia
                contenido = f"Cliente: {cliente.nombre} {cliente.apellido}"
                
                # Actualizar o crear ubicación
                UbicacionUsuario.objects.update_or_create(
                    usuario=request.user,
                    defaults={
                        'latitud': float(latitud),
                        'longitud': float(longitud),
                        'contenido_asociado': contenido,
                    }
                )
            
            messages.success(
                request, 
                f'✅ Cliente {cliente.nombre_completo} (C.I: {cliente.cedula}) creado exitosamente.'
            )
            return redirect('lista_clientes')
        else:
            messages.error(
                request,
                '❌ Error al crear el cliente. Por favor revise los campos.'
            )
    else:
        form = ClientePotencialForm(es_creacion=True)
    
    # Obtener la fecha actual para el template
    today = timezone.now().date()
    
    return render(request, 'Vendedores/crear_clientes.html', {
        'form': form,
        'titulo': 'Nuevo Cliente Potencial',
        'subtitulo': 'Registrar nuevo cliente en el sistema',
        'boton_texto': 'Guardar Cliente',
        'es_creacion': True,
        'today': today,  # 👈 IMPORTANTE: pasar today al template
    })

    
    
    
@login_required
def verificar_cedula(request, cedula):
    """Verifica si una cédula ya está registrada"""
    try:
        cliente = ClientePotencial.objects.select_related('creado_por').get(cedula=cedula)
        data = {
            'existe': True,
            'cliente': {
                'nombre': cliente.nombre,
                'apellido': cliente.apellido,
                'telefono': cliente.telefono,
                'fecha_registro': cliente.fecha_registro.strftime('%d/%m/%Y'),
                'creado_por': cliente.creado_por.username if cliente.creado_por else 'Sistema'
            }
        }
    except ClientePotencial.DoesNotExist:
        data = {'existe': False}
    
    return JsonResponse(data)    


@login_required
def datos_cliente(request, cliente_id):
    """API para obtener datos de un cliente en formato JSON"""
    
    cliente = get_object_or_404(ClientePotencial, id=cliente_id)
    
    # Verificar permisos
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    if not (es_admin or cliente.creado_por == request.user):
        return JsonResponse({'error': 'No tienes permiso para ver este cliente'}, status=403)
    
    # Calcular días desde registro
    dias_desde_registro = (timezone.now().date() - cliente.fecha_registro).days
    today = timezone.now().date()
    data = {
        'id': cliente.id,
        'nombre': cliente.nombre,
        'apellido': cliente.apellido,
        'cedula': cliente.cedula,
        'telefono': cliente.telefono,
        'direccion': cliente.direccion,
        'interesado': cliente.interesado,
        'get_interesado_display': cliente.get_interesado_display(),
        'posee_internet': cliente.posee_internet,
        'fecha_registro': cliente.fecha_registro.strftime('%d/%m/%Y'),
        'creado_por': cliente.creado_por.get_full_name() or cliente.creado_por.username if cliente.creado_por else 'Sistema',
        'dias_desde_registro': dias_desde_registro,
        'observacion': cliente.observacion,
        'today': today,
    }
    
    return JsonResponse(data)


@login_required
@admin_required
def editar_cliente(request, cliente_id):
    """Edita un cliente existente - Solo para superuser y administradores"""
    
    # Verificar si el usuario es superuser o administrador
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()):
        # Opción 1: Redirigir con mensaje de error
        messages.error(request, '⛔ Acceso denegado. Solo administradores pueden editar clientes.')
        return redirect('lista_clientes')
        
        # Opción 2: Lanzar error 403 (Forbidden)
        # raise PermissionDenied
    
    cliente = get_object_or_404(ClientePotencial, id=cliente_id)
    
    if request.method == 'POST':
        form = ClientePotencialForm(request.POST, instance=cliente, es_creacion=False)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'✅ Cliente {cliente.nombre_completo} actualizado correctamente.'
            )
            return redirect('lista_clientes')
        else:
            messages.error(
                request,
                '❌ Error al actualizar el cliente. Por favor revise los campos.'
            )
    else:
        form = ClientePotencialForm(instance=cliente, es_creacion=False)
    
    return render(request, 'Vendedores/crear_clientes.html', {
        'form': form,
        'titulo': 'Editar Cliente',
        'subtitulo': f'Modificando datos de {cliente.nombre_completo}',
        'boton_texto': 'Actualizar Cliente',
        'es_creacion': False,
        'cliente': cliente
    })


@login_required
def capturar_ubicacion_vendedor(request):
    """API para capturar la ubicación del vendedor automáticamente al cargar el formulario"""
    if request.method == 'POST':
        data = json.loads(request.body)
        latitud = data.get('latitud')
        longitud = data.get('longitud')
        
        if latitud and longitud:
            # Guardar la ubicación en la tabla UbicacionUsuario del vendedor
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
def api_ubicaciones(request):
    """API para obtener ubicaciones en formato JSON para actualización automática"""
    
    # Verificar permisos (solo administradores)
    if not (request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    # Obtener filtros de la URL
    tipo = request.GET.get('tipo', 'todos')
    buscar = request.GET.get('buscar', '')
    
    # Base query
    ubicaciones = UbicacionUsuario.objects.select_related('usuario').all()
    
    # Filtrar por tipo de usuario (grupo)
    if tipo and tipo != 'todos':
        ubicaciones = ubicaciones.filter(usuario__groups__name=tipo)
    
    # Filtrar por búsqueda (nombre de usuario, nombre, apellido)
    if buscar:
        ubicaciones = ubicaciones.filter(
            Q(usuario__username__icontains=buscar) |
            Q(usuario__first_name__icontains=buscar) |
            Q(usuario__last_name__icontains=buscar)
        )
    
    # Preparar datos para el mapa
    datos_mapa = []
    for ubicacion in ubicaciones:
        # Obtener el grupo del usuario
        grupo = ubicacion.usuario.groups.first()
        tipo_usuario = grupo.name if grupo else 'Sin grupo'
        
        # Calcular total de clientes del usuario
        total_clientes = ClientePotencial.objects.filter(creado_por=ubicacion.usuario).count()
        
        # Determinar si está activo (última hora)
        hace_una_hora = timezone.now() - timedelta(hours=1)
        activo = ubicacion.ultima_actualizacion > hace_una_hora
        
        datos_mapa.append({
            'usuario': {
                'id': ubicacion.usuario.id,
                'username': ubicacion.usuario.username,
                'first_name': ubicacion.usuario.first_name,
                'last_name': ubicacion.usuario.last_name,
                'tipo': tipo_usuario,
            },
            'latitud': ubicacion.latitud,
            'longitud': ubicacion.longitud,
            'ultima_actualizacion': ubicacion.ultima_actualizacion.isoformat(),
            'activo': activo,
            'total_clientes': total_clientes,
        })
    
    # Calcular estadísticas
    total_usuarios = ubicaciones.count()
    
    hace_1hora = timezone.now() - timedelta(hours=1)
    activos_ahora = ubicaciones.filter(ultima_actualizacion__gte=hace_1hora).count()
    
    # Estadísticas por tipo de usuario
    stats_por_tipo = []
    for grupo in Group.objects.all():
        count = ubicaciones.filter(usuario__groups=grupo).count()
        if count > 0:
            stats_por_tipo.append({
                'nombre': grupo.name,
                'cantidad': count,
            })
    
    # Agregar usuarios sin grupo si existen
    sin_grupo = ubicaciones.filter(usuario__groups__isnull=True).count()
    if sin_grupo > 0:
        stats_por_tipo.append({
            'nombre': 'Sin grupo',
            'cantidad': sin_grupo,
        })
    
    return JsonResponse({
        'ubicaciones': datos_mapa,
        'total_usuarios': total_usuarios,
        'activos_ahora': activos_ahora,
        'stats_por_tipo': stats_por_tipo,
        'timestamp': timezone.now().isoformat(),
    })    
    
    
# ===============Zona de contrato====================== 

@login_required
def verificar_cliente_contrato(request, cedula):
    """Verifica si existe un cliente potencial con la cédula dada"""
    
    try:
        cliente = ClientePotencial.objects.get(cedula=cedula)
        
        # Verificar si ya tiene contrato
        tiene_contrato = ContratoCliente.objects.filter(cliente_potencial=cliente).exists()
        
        return JsonResponse({
            'existe': True,
            'cliente': {
                'id': cliente.id,
                'nombre': cliente.nombre,
                'apellido': cliente.apellido,
                'cedula': cliente.cedula,
                'telefono': cliente.telefono,
                'direccion': cliente.direccion,
            },
            'tiene_contrato': tiene_contrato
        })
    except ClientePotencial.DoesNotExist:
        return JsonResponse({'existe': False})

@login_required
def crear_contrato(request):
    """Vista para crear contrato con verificación de cédula primero"""
    
    if request.method == 'POST':
        # Verificar que viene el ID del cliente
        cliente_id = request.POST.get('cliente_id')
        if not cliente_id:
            messages.error(request, '❌ Error: Debe verificar un cliente primero.')
            return redirect('crear_contrato')
        
        cliente = get_object_or_404(ClientePotencial, id=cliente_id)
        
        # Pasar el cliente_potencial al formulario
        form = ContratoClienteForm(request.POST, request.FILES, cliente_potencial=cliente)
        
        if form.is_valid():
            contrato = form.save(commit=False)
            contrato.cliente_potencial = cliente
            contrato.creado_por = request.user
            contrato.save()
            
            messages.success(
                request,
                f'✅ Contrato creado exitosamente para {cliente.nombre_completo}'
            )
            return redirect('lista_contratos')
        else:
            # Si hay errores, guardar los datos en la sesión y redirigir con el error
            request.session['form_data'] = request.POST.urlencode()
            request.session['cliente_id'] = cliente.id
            request.session['error_correo'] = 'correo_electronico' in form.errors
            request.session['error_message'] = form.errors.get('correo_electronico', [''])[0] if 'correo_electronico' in form.errors else ''
            
            # También guardar los archivos en sesión (solo los nombres, no los archivos en sí)
            if request.FILES.get('foto_pago'):
                request.session['foto_pago_name'] = request.FILES['foto_pago'].name
            
            return redirect('crear_contrato_error')
    
    # GET request - verificar si hay datos de error en sesión
    form_data = request.session.pop('form_data', None)
    cliente_id = request.session.pop('cliente_id', None)
    error_correo = request.session.pop('error_correo', False)
    error_message = request.session.pop('error_message', '')
    foto_pago_name = request.session.pop('foto_pago_name', None)
    
    if cliente_id and form_data:
        # Venimos de un error, reconstruir el formulario con los datos
        cliente = get_object_or_404(ClientePotencial, id=cliente_id)
        
        from django.http import QueryDict
        data = QueryDict(form_data)
        
        form = ContratoClienteForm(data, request.FILES, cliente_potencial=cliente)
        
        context = {
            'form': form,
            'cliente': cliente,
            'cliente_verificado': True,
            'titulo': 'Nuevo Contrato',
            'subtitulo': f'Contrato para {cliente.nombre_completo}',
            'boton_texto': 'Guardar Contrato',
            'es_pagina_crear': True,
            'es_post_error': True,
            'error_correo': error_correo,
            'error_message': error_message,
            'foto_pago_name': foto_pago_name,
        }
    else:
        # GET normal - empezar desde cero
        context = {
            'form': ContratoClienteForm(),
            'titulo': 'Nuevo Contrato',
            'subtitulo': 'Verifique el cliente para continuar',
            'boton_texto': 'Guardar Contrato',
            'cliente_verificado': False,
            'es_pagina_crear': True,
            'es_post_error': False,
        }
    
    return render(request, 'Vendedores/crear_contrato.html', context)

@login_required
def crear_contrato_error(request):
    """Vista intermedia para manejar errores POST"""
    # Esta vista solo redirige a crear_contrato
    # Los datos ya están en la sesión
    return redirect('crear_contrato')
 
@login_required
def lista_contratos(request):
    """Lista de contratos - Vendedor solo ve los suyos, Admin ve todos"""
    
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    # Base query
    if es_admin:
        contratos = ContratoCliente.objects.all().select_related(
            'cliente_potencial', 'creado_por', 'plan_contratado'
        )
        # Lista de vendedores para el filtro (solo admin)
        vendedores = User.objects.filter(is_active=True).order_by('username')
    else:
        contratos = ContratoCliente.objects.filter(creado_por=request.user).select_related(
            'cliente_potencial', 'plan_contratado'
        )
        vendedores = []
    
    # Filtros
    estado = request.GET.get('estado', '')
    if estado:
        contratos = contratos.filter(estado=estado)
    
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        contratos = contratos.filter(
            Q(cliente_potencial__nombre__icontains=busqueda) |
            Q(cliente_potencial__apellido__icontains=busqueda) |
            Q(cliente_potencial__cedula__icontains=busqueda) |
            Q(correo_electronico__icontains=busqueda)
        )
    
    # Filtro por vendedor (solo admin)
    vendedor_id = request.GET.get('vendedor', '')
    if vendedor_id and es_admin:
        contratos = contratos.filter(creado_por_id=vendedor_id)
    
    # Paginación
    paginator = Paginator(contratos, 5)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    
    # Estadísticas
    total_contratos = contratos.count()
    en_proceso = contratos.filter(estado='EN_PROCESO').count()
    completados = contratos.filter(estado='COMPLETADO').count()
    no_completados = contratos.filter(estado='NO_COMPLETADO').count()
    
    context = {
        'page_obj': page_obj,
        'total_contratos': total_contratos,
        'en_proceso': en_proceso,
        'completados': completados,
        'no_completados': no_completados,
        'filtro_estado': estado,
        'filtro_vendedor': vendedor_id,
        'busqueda': busqueda,
        'vendedores': vendedores,
    }
    
    return render(request, 'Vendedores/lista_contratos.html', context)


import traceback
import sys
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

import traceback
import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

@login_required
def datos_contrato(request, contrato_id):
    """API para obtener datos de un contrato - Versión ultra robusta"""
    
    response_data = {}
    status_code = 200
    
    try:
        from myapp.models import ContratoCliente
        
        print(f"=== INICIO datos_contrato ID: {contrato_id} ===")
        
        # 1. Obtener contrato
        contrato = get_object_or_404(ContratoCliente, id=contrato_id)
        
        # 2. Verificar permisos
        es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists() or request.user.groups.filter(name='Supervisor').exists()
        if not (es_admin or contrato.creado_por == request.user):
            return JsonResponse({'error': 'No autorizado'}, status=403)
        
        # 3. Construir data con manejo de errores por campo
        data = {}
        
        # ID
        data['id'] = contrato.id
        
        # Cliente (con try individual)
        try:
            data['cliente'] = {
                'id': contrato.cliente_potencial.id,
                'nombre': str(contrato.cliente_potencial.nombre or ''),
                'apellido': str(contrato.cliente_potencial.apellido or ''),
                'cedula': str(contrato.cliente_potencial.cedula or ''),
                'telefono': str(contrato.cliente_potencial.telefono or ''),
            }
        except Exception as e:
            data['cliente'] = {'error': f'Error en cliente: {str(e)}'}
        
        # Campos simples
        campos_simples = [
            'otro_telefono', 'correo_electronico', 'direccion_detallada',
            'punto_referencia', 'numero_casa', 'numero_pago_movil',
            'ods', 'customer_id', 'atr'
        ]
        for campo in campos_simples:
            try:
                valor = getattr(contrato, campo, '')
                data[campo] = str(valor) if valor else ''
            except:
                data[campo] = ''
        
        # Fecha nacimiento
        try:
            data['fecha_nacimiento'] = contrato.fecha_nacimiento.strftime('%d/%m/%Y') if contrato.fecha_nacimiento else ''
        except:
            data['fecha_nacimiento'] = ''
        
        # Plan
        try:
            data['plan'] = {
                'id': contrato.plan_contratado.id,
                'nombre': str(contrato.plan_contratado.nombre or '')
            }
        except:
            data['plan'] = {'id': 0, 'nombre': 'Error'}
        
        # Simple plus
        try:
            data['simple_plus'] = contrato.get_simple_plus_display() or ''
        except:
            data['simple_plus'] = ''
        
        # Modalidad equipo
        try:
            data['modalidad_equipo'] = str(contrato.modalidad_equipo.nombre) if contrato.modalidad_equipo else ''
        except:
            data['modalidad_equipo'] = ''
        
        # Tipo vivienda
        try:
            data['tipo_vivienda'] = str(contrato.tipo_vivienda.nombre) if contrato.tipo_vivienda else ''
        except:
            data['tipo_vivienda'] = ''
        
        # Red
        try:
            data['red'] = str(contrato.red.nombre) if contrato.red else ''
        except:
            data['red'] = ''
        
        # Foto (importante: NO intentar acceder a .url si no existe)
        try:
            if contrato.foto_pago and hasattr(contrato.foto_pago, 'url'):
                data['foto_pago'] = contrato.foto_pago.url
            else:
                data['foto_pago'] = None
        except:
            data['foto_pago'] = None
        
        # Estado
        try:
            data['estado'] = contrato.get_estado_display() or ''
        except:
            data['estado'] = ''
        
        # Creado por
        try:
            if contrato.creado_por:
                data['creado_por'] = contrato.creado_por.get_full_name() or contrato.creado_por.username
            else:
                data['creado_por'] = 'Sistema'
        except:
            data['creado_por'] = 'Desconocido'
        
        # Fechas
        try:
            data['fecha_creacion'] = contrato.fecha_creacion.strftime('%d/%m/%Y %H:%M')
        except:
            data['fecha_creacion'] = ''
        
        try:
            data['fecha_actualizacion'] = contrato.fecha_actualizacion.strftime('%d/%m/%Y %H:%M')
        except:
            data['fecha_actualizacion'] = ''
        
        response_data = data
        
    except Exception as e:
        status_code = 500
        response_data = {
            'error': str(e),
            'tipo_error': type(e).__name__,
            'mensaje': f'Error al cargar el contrato {contrato_id}: {str(e)}'
        }
        print(f"ERROR: {traceback.format_exc()}")
    
    # Asegurarnos de que SIEMPRE devolvemos JSON
    try:
        return JsonResponse(response_data, status=status_code)
    except Exception as json_error:
        return JsonResponse({
            'error': 'Error al serializar respuesta',
            'detalle': str(json_error)
        }, status=500)
    
    
    
@login_required
def estado_cuadrillas(request):
    """
    Vista para vendedores - Muestra el estado de las cuadrillas y sus instalaciones
    Incluye tanto contratos de vendedor como ventas directas
    """
    
    # Verificar que el usuario sea vendedor o administrador
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_vendedor = request.user.groups.filter(name='Vendedor').exists()
    es_supervisor =request.user.groups.filter(name='Supervisor').exists()
    if not (es_admin or es_vendedor or es_supervisor):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Obtener todas las cuadrillas activas
    cuadrillas = Cuadrilla.objects.filter(activo=True).prefetch_related(
        'instaladores__usuario',
        'asignaciones__contrato__cliente_potencial',
        'asignaciones__venta_directa',
        'asignaciones__instalacion'
    )
    
    # Estadísticas generales
    total_cuadrillas = cuadrillas.count()
    cuadrillas_disponibles = cuadrillas.filter(estado='DISPONIBLE').count()
    cuadrillas_ocupadas = cuadrillas.filter(estado='OCUPADO').count()
    cuadrillas_descanso = cuadrillas.filter(estado='DESCANSO').count()
    
    # Datos por cuadrilla
    datos_cuadrillas = []
    for cuadrilla in cuadrillas:
        # Obtener asignaciones de esta cuadrilla (incluye contratos y ventas directas)
        asignaciones = AsignacionContrato.objects.filter(
            cuadrilla=cuadrilla,
            activo=True
        ).select_related(
            'contrato__cliente_potencial',
            'contrato__plan_contratado',
            'venta_directa',
            'instalacion'
        )
        
        # Contar instalaciones por estado
        total_asignaciones = asignaciones.count()
        instalaciones_pendientes = 0
        instalaciones_completadas = 0
        
        for asignacion in asignaciones:
            try:
                if asignacion.instalacion.completada:
                    instalaciones_completadas += 1
                else:
                    instalaciones_pendientes += 1
            except:
                instalaciones_pendientes += 1
        
        # Instalaciones de hoy
        hoy = timezone.now().date()
        instalaciones_hoy = asignaciones.filter(
            fecha_asignacion__date=hoy
        ).count()
        
        # Instalaciones de la semana
        semana_pasada = hoy - timedelta(days=7)
        instalaciones_semana = asignaciones.filter(
            fecha_asignacion__date__gte=semana_pasada
        ).count()
        
        # Última instalación
        ultima_instalacion = asignaciones.order_by('-fecha_asignacion').first()
        ultima_instalacion_info = None
        if ultima_instalacion:
            # Obtener nombre del cliente según el tipo
            if ultima_instalacion.contrato:
                cliente_nombre = ultima_instalacion.contrato.cliente_potencial.nombre_completo
            else:
                cliente_nombre = ultima_instalacion.venta_directa.nombre_completo
            
            ultima_instalacion_info = {
                'cliente': cliente_nombre,
                'fecha': ultima_instalacion.fecha_asignacion,
                'estado': 'Completada' if hasattr(ultima_instalacion, 'instalacion') and ultima_instalacion.instalacion.completada else 'Pendiente'
            }
        
        # Calcular porcentaje de eficiencia
        eficiencia = 0
        if total_asignaciones > 0:
            eficiencia = int((instalaciones_completadas / total_asignaciones) * 100)
        
        # Obtener lista de instaladores
        instaladores_list = []
        for inst in cuadrilla.instaladores.all():
            nombre = inst.usuario.get_full_name() or inst.usuario.username
            instaladores_list.append(nombre)
        
        datos_cuadrillas.append({
            'id': cuadrilla.id,
            'nombre': cuadrilla.nombre,
            'codigo': cuadrilla.codigo,
            'estado': cuadrilla.estado,
            'estado_display': cuadrilla.get_estado_display(),
            'cantidad_instaladores': cuadrilla.cantidad_instaladores,
            'instaladores': instaladores_list,
            'total_asignaciones': total_asignaciones,
            'instalaciones_pendientes': instalaciones_pendientes,
            'instalaciones_completadas': instalaciones_completadas,
            'instalaciones_hoy': instalaciones_hoy,
            'instalaciones_semana': instalaciones_semana,
            'eficiencia': eficiencia,
            'ultima_instalacion': ultima_instalacion_info,
        })
    
    # Ordenar por estado y eficiencia
    orden_estado = {'DISPONIBLE': 1, 'OCUPADO': 2, 'DESCANSO': 3}
    datos_cuadrillas.sort(key=lambda x: (orden_estado.get(x['estado'], 4), -x['eficiencia']))
    
    context = {
        'cuadrillas': datos_cuadrillas,
        'total_cuadrillas': total_cuadrillas,
        'cuadrillas_disponibles': cuadrillas_disponibles,
        'cuadrillas_ocupadas': cuadrillas_ocupadas,
        'cuadrillas_descanso': cuadrillas_descanso,
        'es_admin': es_admin,
    }
    return render(request, 'Vendedores/estado_cuadrillas.html', context)



@login_required
@csrf_exempt
def completar_pago(request, contrato_id):
    """API para completar el pago del contrato"""
    if request.method == 'GET':
        return JsonResponse({
            'status': 'debug', 
            'message': 'La vista funciona, el problema es el método POST',
            'contrato_id': contrato_id
        })
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    contrato = get_object_or_404(ContratoCliente, id=contrato_id)
    
    
    
    
    try:
        numero_pago_movil = request.POST.get('numero_pago_movil', '').strip()
        foto_pago = request.FILES.get('foto_pago')
        
        # Validar que al menos un campo tenga información
        if not numero_pago_movil and not foto_pago:
            return JsonResponse({'error': 'Debes proporcionar al menos el número de pago móvil o la foto del comprobante'}, status=400)
        
        # Guardar número de pago móvil
        if numero_pago_movil:
            contrato.numero_pago_movil = numero_pago_movil
        
        # Guardar foto del pago
        if foto_pago:
            # Validar tipo de archivo
            extension = os.path.splitext(foto_pago.name)[1].lower()
            if extension not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                return JsonResponse({'error': 'Formato de imagen no válido. Usa JPG, PNG, GIF o WEBP'}, status=400)
            
            # Validar tamaño (máximo 5MB)
            if foto_pago.size > 5 * 1024 * 1024:
                return JsonResponse({'error': 'La imagen no debe superar los 5MB'}, status=400)
            
            contrato.foto_pago = foto_pago
        
        contrato.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Información de pago actualizada correctamente',
            'numero_pago_movil': contrato.numero_pago_movil,
            'foto_pago_url': contrato.foto_pago.url if contrato.foto_pago else None
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)