# views_venta_directa.py
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from .models import VentaDirecta, Plan, Cuadrilla, AsignacionContrato
from .forms import VentaDirectaForm
import datetime


@login_required
def lista_ventas_directas(request):
    """Lista de ventas directas"""
    
    # Verificar permisos
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_torre_control = request.user.groups.filter(name='TorreControl').exists()
    
    if not (es_admin or es_torre_control):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Base query
    ventas = VentaDirecta.objects.select_related('plan', 'creado_por').all()
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        ventas = ventas.filter(
            Q(nro_orden__icontains=busqueda) |
            Q(cedula__icontains=busqueda) |
            Q(customer_id__icontains=busqueda) |
            Q(nombre__icontains=busqueda) |
            Q(apellido__icontains=busqueda) |
            Q(telefono__icontains=busqueda)
        )
    
    estado = request.GET.get('estado', '')
    if estado:
        ventas = ventas.filter(estado=estado)
    
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    if fecha_desde:
        ventas = ventas.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        ventas = ventas.filter(fecha__lte=fecha_hasta)
    
    # Paginación
    paginator = Paginator(ventas, 10)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    
    # Estadísticas
    total = ventas.count()
    en_proceso = ventas.filter(estado='EN_PROCESO').count()
    completadas = ventas.filter(estado='COMPLETADO').count()
    no_completadas = ventas.filter(estado='NO_COMPLETADO').count()
    
    context = {
        'page_obj': page_obj,
        'total': total,
        'en_proceso': en_proceso,
        'completadas': completadas,
        'no_completadas': no_completadas,
        'busqueda': busqueda,
        'estado_filtro': estado,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'es_admin': es_admin,
    }
    return render(request, 'Admin/ventas_directa/venta_directa.html', context)


@login_required
def crear_venta_directa(request):
    """Crear una nueva venta directa"""
    
    es_admin_user = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    if not es_admin_user:
        messages.error(request, 'No tienes permisos para crear ventas directas.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = VentaDirectaForm(request.POST)
        if form.is_valid():
            venta = form.save(commit=False)
            venta.creado_por = request.user
            venta.save()
            
            messages.success(request, f'✅ Venta directa #{venta.nro_orden} creada exitosamente para {venta.nombre_completo}.')
            return redirect('lista_ventas_directas')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Error en {field}: {error}')
    else:
        # Ya no se genera número automático, se deja vacío para que el usuario lo ingrese
        form = VentaDirectaForm()
    
    context = {
        'form': form,
        'titulo': 'Nueva Venta Directa',
        'subtitulo': 'Registrar una nueva venta desde la torre de control',
        'boton_texto': 'Guardar Venta',
    }
    return render(request, 'Admin/ventas_directa/crear_venta_directa.html', context)


@login_required
def editar_venta_directa(request, venta_id):
    """Editar una venta directa existente"""
    
    es_admin_user = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    if not es_admin_user:
        messages.error(request, 'No tienes permisos para editar ventas directas.')
        return redirect('lista_ventas_directas')
    
    venta = get_object_or_404(VentaDirecta, id=venta_id)
    
    if request.method == 'POST':
        form = VentaDirectaForm(request.POST, instance=venta)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Venta directa #{venta.nro_orden} actualizada correctamente.')
            return redirect('lista_ventas_directas')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Error en {field}: {error}')
    else:
        form = VentaDirectaForm(instance=venta)
    
    context = {
        'form': form,
        'venta': venta,
        'titulo': 'Editar Venta Directa',
        'subtitulo': f'Editando venta #{venta.nro_orden}',
        'boton_texto': 'Actualizar Venta',
    }
    return render(request, 'Admin/ventas_directa/crear_venta_directa.html', context)


@login_required
def crear_venta_rapida(request):
    """Crear venta directa automáticamente desde texto formateado"""
    
    es_admin_user = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    if not es_admin_user:
        messages.error(request, 'No tienes permisos para crear ventas directas.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        import json
        import re
        from .models import VentaDirecta, Plan
        
        datos_json = request.POST.get('datos_json', '{}')
        observacion = request.POST.get('observacion', '')
        
        try:
            datos = json.loads(datos_json)
        except:
            messages.error(request, 'Error al procesar los datos')
            return redirect('lista_ventas_directas')
        
        # Separar nombre y apellido
        nombre_completo = datos.get('nombre_completo', '').strip()
        if nombre_completo:
            partes = nombre_completo.split()
            if len(partes) == 1:
                nombre = partes[0]
                apellido = ''
            elif len(partes) == 2:
                nombre = partes[0]
                apellido = partes[1]
            else:
                nombre = ' '.join(partes[:-1])
                apellido = partes[-1]
        else:
            nombre = ''
            apellido = ''
        
        # Validar campos requeridos
        nro_orden = datos.get('nro_orden', '').strip()
        cedula = re.sub(r'[^0-9]', '', datos.get('cedula', '')) if datos.get('cedula') else ''
        customer_id = datos.get('customer_id', '').strip()
        telefono_raw = datos.get('telefono', '').strip()
        
        # Formatear teléfono si es necesario (si viene sin guion)
        if telefono_raw and len(telefono_raw) == 10 and '-' not in telefono_raw:
            telefono = f"{telefono_raw[:4]}-{telefono_raw[4:]}"
        else:
            telefono = telefono_raw
        
        # Buscar el plan
        plan_nombre = datos.get('plan', '').strip()
        plan = None
        if plan_nombre:
            numeros = re.findall(r'\d+', plan_nombre)
            if numeros:
                plan = Plan.objects.filter(nombre__icontains=numeros[0]).first()
        
        if not plan:
            plan = Plan.objects.filter(activo=True).first()
        
        # Crear venta
        try:
            venta = VentaDirecta.objects.create(
                nro_orden=nro_orden if nro_orden else 'N/A',
                cedula=cedula if cedula else 'N/A',
                customer_id=customer_id if customer_id else 'N/A',
                nombre=nombre if nombre else 'N/A',
                apellido=apellido if apellido else 'N/A',
                telefono=telefono if telefono else 'N/A',
                plan=plan,
                observacion=observacion if observacion else '',
                creado_por=request.user
            )
            
            messages.success(request, f'✅ Venta directa #{venta.nro_orden} creada exitosamente para {venta.nombre_completo}')
            
        except Exception as e:
            messages.error(request, f'Error al crear la venta: {str(e)}')
        
        return redirect('lista_ventas_directas')
    
    return redirect('lista_ventas_directas')


@login_required
def detalle_venta_directa(request, venta_id):
    """Ver detalle de una venta directa (API JSON)"""
    
    es_admin_user = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_torre_control = request.user.groups.filter(name='TorreControl').exists()
    
    if not (es_admin_user or es_torre_control):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    venta = get_object_or_404(VentaDirecta, id=venta_id)
    
    # Verificar si está asignada
    asignacion = AsignacionContrato.objects.filter(venta_directa=venta, activo=True).first()
    
    data = {
        'id': venta.id,
        'nro_orden': venta.nro_orden,
        'cedula': venta.cedula,
        'customer_id': venta.customer_id or '',
        'nombre': venta.nombre,
        'apellido': venta.apellido,
        'nombre_completo': venta.nombre_completo,
        'telefono': venta.telefono,
        'plan': {
            'id': venta.plan.id,
            'nombre': venta.plan.nombre,
        },
        'estado': venta.get_estado_display(),
        'estado_valor': venta.estado,
        'fecha': venta.fecha.strftime('%d/%m/%Y'),
        'observacion': venta.observacion or '',
        
        
        'creado_por': venta.creado_por.get_full_name() or venta.creado_por.username if venta.creado_por else 'Sistema',
        'fecha_creacion': venta.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        'fecha_actualizacion': venta.fecha_actualizacion.strftime('%d/%m/%Y %H:%M'),
    }
    
    return JsonResponse(data)


@login_required
def cambiar_estado_venta(request, venta_id):
    """Cambiar el estado de una venta directa"""
    
    es_admin_user = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    if not es_admin_user:
        messages.error(request, 'No tienes permisos para cambiar el estado de ventas.')
        return redirect('lista_ventas_directas')
    
    venta = get_object_or_404(VentaDirecta, id=venta_id)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        
        if nuevo_estado in ['EN_PROCESO', 'COMPLETADO', 'NO_COMPLETADO']:
            venta.estado = nuevo_estado
            venta.save(update_fields=['estado'])
            
            estado_display = venta.get_estado_display()
            messages.success(request, f'✅ Venta #{venta.nro_orden} actualizada a estado: {estado_display}')
        else:
            messages.error(request, '❌ Estado no válido')
        
        return redirect('lista_ventas_directas')
    
    context = {
        'venta': venta,
    }
    return render(request, 'Admin/ventas_directas/cambiar_estado_venta.html', context)