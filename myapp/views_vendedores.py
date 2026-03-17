from email.headerregistry import Group
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
    paginator = Paginator(clientes, 15)
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
    
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import Group
from .models import UbicacionUsuario, ClientePotencial

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
        
        # 👇 VERIFICACIÓN DE PERMISOS MODIFICADA
        # Ya NO verificamos que el cliente sea del vendedor actual
        # CUALQUIER vendedor puede crear contratos para CUALQUIER cliente potencial
        # Solo verificamos que el usuario esté autenticado (ya lo hace @login_required)
        
        # Pasar el cliente_potencial al formulario
        form = ContratoClienteForm(request.POST, request.FILES, cliente_potencial=cliente)
        
        if form.is_valid():
            contrato = form.save(commit=False)
            contrato.cliente_potencial = cliente
            contrato.creado_por = request.user  # El que crea el contrato es el vendedor actual
            contrato.save()
            
            messages.success(
                request,
                f'✅ Contrato creado exitosamente para {cliente.nombre_completo}'
            )
            return redirect('lista_contratos')
        else:
            # Manejar error específico de correo
            if 'correo_electronico' in form.errors:
                error_msg = form.errors['correo_electronico'][0]
                messages.error(request, f'correo_duplicado:{error_msg}')
            else:
                # Mostrar otros errores
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'Error en {field}: {error}')
            
            # Guardar los datos en la sesión para mantenerlos después del redirect
            request.session['form_data'] = request.POST.urlencode()
            request.session['cliente_id'] = cliente.id
            request.session['error_correo'] = 'correo_electronico' in form.errors
            
            return redirect('crear_contrato_error')
    
    # GET request - verificar si hay datos de error en sesión
    form_data = request.session.pop('form_data', None)
    cliente_id = request.session.pop('cliente_id', None)
    error_correo = request.session.pop('error_correo', False)
    
    if cliente_id and form_data:
        # Venimos de un error, reconstruir el formulario con los datos
        cliente = get_object_or_404(ClientePotencial, id=cliente_id)
        
        from django.http import QueryDict
        data = QueryDict(form_data)
        # Nota: Los archivos no se pueden guardar en sesión, es una limitación
        
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
    paginator = Paginator(contratos, 10)
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


@login_required
def datos_contrato(request, contrato_id):
    """API para obtener datos de un contrato en formato JSON"""
    
    try:
        contrato = get_object_or_404(
            ContratoCliente.objects.select_related(
                'cliente_potencial', 'plan_contratado', 'modalidad_equipo',
                'tipo_vivienda', 'red', 'creado_por'
            ),
            id=contrato_id
        )
        
        # Verificar permisos
        es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
        if not (es_admin or contrato.creado_por == request.user):
            return JsonResponse({'error': 'No autorizado'}, status=403)
        
        # CONSTRUIR URL DE LA FOTO (VERSIÓN SIMPLIFICADA)
        foto_url = None
        if contrato.foto_pago:
            try:
                # Usar el método url de Django
                foto_url = contrato.foto_pago.url
                print(f"✅ URL generada por Django: {foto_url}")
                print(f"📁 Ruta del archivo: {contrato.foto_pago.path}")
            except Exception as e:
                print(f"❌ Error con foto_pago.url: {e}")
                # Fallback manual
                nombre_archivo = str(contrato.foto_pago)
                if nombre_archivo.startswith('pagos/'):
                    nombre_archivo = nombre_archivo.replace('pagos/', '')
                foto_url = f'/pagos/{nombre_archivo}'
                print(f"⚠️ URL manual: {foto_url}")
        
        # Preparar datos para el JSON
        data = {
            'id': contrato.id,
            'cliente': {
                'id': contrato.cliente_potencial.id,
                'nombre': contrato.cliente_potencial.nombre,
                'apellido': contrato.cliente_potencial.apellido,
                'cedula': contrato.cliente_potencial.cedula,
                'telefono': contrato.cliente_potencial.telefono,
            },
            'otro_telefono': contrato.otro_telefono or '',
            'correo_electronico': contrato.correo_electronico or '',
            'direccion_detallada': contrato.direccion_detallada or '',
            'fecha_nacimiento': contrato.fecha_nacimiento.strftime('%d/%m/%Y') if contrato.fecha_nacimiento else '',
            'plan': {
                'id': contrato.plan_contratado.id,
                'nombre': contrato.plan_contratado.nombre,
            },
            'simple_plus': contrato.get_simple_plus_display(),
            'modalidad_equipo': contrato.modalidad_equipo.nombre if contrato.modalidad_equipo else '',
            'punto_referencia': contrato.punto_referencia or '',
            'tipo_vivienda': contrato.tipo_vivienda.nombre if contrato.tipo_vivienda else '',
            'numero_casa': contrato.numero_casa or '',
            'numero_pago_movil': contrato.numero_pago_movil or '',
            'foto_pago': foto_url,
            'red': contrato.red.nombre if contrato.red else '',
            'ods': contrato.ods or '',
            'customer_id': contrato.customer_id or '',
            'atr': contrato.atr or '',
            'estado': contrato.get_estado_display(),
            'creado_por': contrato.creado_por.get_full_name() or contrato.creado_por.username if contrato.creado_por else 'Sistema',
            'fecha_creacion': contrato.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            'fecha_actualizacion': contrato.fecha_actualizacion.strftime('%d/%m/%Y %H:%M'),
        }
        
        print(f"📤 Enviando datos. Foto URL: {foto_url}")
        return JsonResponse(data)
        
    except Exception as e:
        print(f"❌ Error en datos_contrato: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)