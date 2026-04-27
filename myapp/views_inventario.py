# ==================== VISTAS DE INVENTARIO ====================

from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db import transaction
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from myapp.decorators import admin_required
from myapp.models import Cuadrilla, Instalacion, InventarioCuadrilla, InventarioGlobal, Material, MovimientoInventario, Soporte

@login_required
@staff_member_required  # Solo administradores pueden acceder
def inventario_global_lista(request):
    """Vista para listar y gestionar el inventario global"""
    
    # Verificar permisos (solo administradores)
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    if not es_admin:
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Obtener todos los materiales con su inventario
    inventario_list = []
    materiales = Material.objects.filter(activo=True).order_by('nombre')
    
    for material in materiales:
        inv_global, created = InventarioGlobal.objects.get_or_create(material=material)
        inventario_list.append({
            'material': material,
            'inventario': inv_global
        })
    
    # Paginación
    paginator = Paginator(inventario_list, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'inventario_list': page_obj,
        'total_materiales': materiales.count(),
        'total_cantidad': sum(item['inventario'].cantidad for item in inventario_list),
        'bajo_stock': [item for item in inventario_list if item['inventario'].esta_bajo_stock],
    }
    return render(request, 'Inventario/inventario_global_lista.html', context)


@login_required
@staff_member_required
def inventario_global_agregar(request):
    """Vista para agregar materiales al inventario global"""
    
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    if not es_admin:
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        material_id = request.POST.get('material')
        cantidad = request.POST.get('cantidad')
        observacion = request.POST.get('observacion', '')
        
        # Validar datos
        if not material_id or not cantidad:
            messages.error(request, 'Debes seleccionar un material y especificar una cantidad.')
            return redirect('inventario_global_agregar')
        
        try:
            cantidad = int(cantidad)
            if cantidad <= 0:
                messages.error(request, 'La cantidad debe ser mayor a 0.')
                return redirect('inventario_global_agregar')
        except ValueError:
            messages.error(request, 'La cantidad debe ser un número válido.')
            return redirect('inventario_global_agregar')
        
        with transaction.atomic():
            material = Material.objects.get(id=material_id)
            inv_global, created = InventarioGlobal.objects.get_or_create(material=material)
            
            # Sumar al inventario global
            inv_global.cantidad += cantidad
            inv_global.actualizado_por = request.user
            inv_global.save()
            
            # Registrar movimiento
            MovimientoInventario.objects.create(
                material=material,
                tipo=MovimientoInventario.TipoMovimiento.ENTRADA,
                cantidad=cantidad,
                realizado_por=request.user,
                observacion=observacion or f"Adición de {cantidad} unidades al inventario global"
            )
        
        messages.success(request, f'✅ Se agregaron {cantidad} unidades de "{material.nombre}" al inventario global.')
        return redirect('inventario_global_lista')
    
    # GET: Mostrar formulario
    materiales = Material.objects.filter(activo=True).order_by('nombre')
    
    # Crear materiales base si no existen
    materiales_base = [
          # Para modelo_modem
        "Conector",
        "Roseta", 
        "Patch Cord",
        "Tensor",
        "Fibra Optica (metros)"
    ]
    
    for nombre in materiales_base:
        Material.objects.get_or_create(nombre=nombre)
    
    context = {
        'materiales': materiales,
        'tipos_movimiento': MovimientoInventario.TipoMovimiento.choices,
    }
    return render(request, 'Inventario/inventario_global_agregar.html', context)


@login_required
@staff_member_required
def inventario_global_ajustar(request, material_id):
    """Vista para ajustar manualmente la cantidad de un material"""
    
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    if not es_admin:
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    material = get_object_or_404(Material, id=material_id, activo=True)
    inv_global, created = InventarioGlobal.objects.get_or_create(material=material)
    
    if request.method == 'POST':
        nueva_cantidad = request.POST.get('cantidad')
        observacion = request.POST.get('observacion', '')
        
        try:
            nueva_cantidad = int(nueva_cantidad)
            if nueva_cantidad < 0:
                messages.error(request, 'La cantidad no puede ser negativa.')
                return redirect('inventario_global_ajustar', material_id=material_id)
        except ValueError:
            messages.error(request, 'La cantidad debe ser un número válido.')
            return redirect('inventario_global_ajustar', material_id=material_id)
        
        with transaction.atomic():
            diferencia = nueva_cantidad - inv_global.cantidad
            
            inv_global.cantidad = nueva_cantidad
            inv_global.actualizado_por = request.user
            inv_global.save()
            
            if diferencia != 0:
                MovimientoInventario.objects.create(
                    material=material,
                    tipo=MovimientoInventario.TipoMovimiento.AJUSTE,
                    cantidad=diferencia,
                    realizado_por=request.user,
                    observacion=observacion or f"Ajuste manual: {inv_global.cantidad} → {nueva_cantidad}"
                )
        
        messages.success(request, f'✅ Cantidad de "{material.nombre}" actualizada a {nueva_cantidad} unidades.')
        return redirect('inventario_global_lista')
    
    context = {
        'material': material,
        'inventario': inv_global,
    }
    return render(request, 'Inventario/inventario_global_ajustar.html', context)


@login_required
@staff_member_required
def inventario_movimientos(request):
    """Vista para ver los movimientos del inventario global"""
    
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    if not es_admin:
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Filtros
    tipo_filtro = request.GET.get('tipo', '')
    material_filtro = request.GET.get('material', '')
    cuadrilla_filtro = request.GET.get('cuadrilla', '')
    
    # ========== SOLO MOVIMIENTOS QUE AFECTAN AL INVENTARIO GLOBAL ==========
    # Excluir GASTO_INSTALACION y GASTO_SOPORTE (son gastos internos de cuadrillas)
    movimientos = MovimientoInventario.objects.select_related('material', 'cuadrilla', 'realizado_por').exclude(
        tipo__in=['GASTO_INSTALACION', 'GASTO_SOPORTE']
    )
    
    if tipo_filtro:
        movimientos = movimientos.filter(tipo=tipo_filtro)
    
    if material_filtro:
        movimientos = movimientos.filter(material_id=material_filtro)
    
    if cuadrilla_filtro:
        movimientos = movimientos.filter(cuadrilla_id=cuadrilla_filtro)
    
    movimientos = movimientos.order_by('-fecha_movimiento')
    
    # Paginación
    paginator = Paginator(movimientos, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    materiales = Material.objects.filter(activo=True).order_by('nombre')
    cuadrillas = Cuadrilla.objects.filter(activo=True).order_by('nombre')
    
    # Resumen de movimientos (solo los que afectan al global)
    total_movimientos = movimientos.count()
    total_entradas = movimientos.filter(tipo='ENTRADA').count()
    total_salidas = movimientos.filter(tipo='SALIDA_A_CUADRILLA').count()
    total_devoluciones = movimientos.filter(tipo='DEVOLUCION_CUADRILLA').count()
    
    context = {
        'movimientos': page_obj,
        'materiales': materiales,
        'cuadrillas': cuadrillas,
        'tipos_movimiento': MovimientoInventario.TipoMovimiento.choices,
        'tipo_filtro': tipo_filtro,
        'material_filtro': material_filtro,
        'cuadrilla_filtro': cuadrilla_filtro,
        'total_movimientos': total_movimientos,
        'total_entradas': total_entradas,
        'total_salidas': total_salidas,
        'total_devoluciones': total_devoluciones,
    }
    return render(request, 'Inventario/inventario_movimientos.html', context)


# ==================== ASIGNAR MATERIALES A CUADRILLAS ====================

@login_required
@staff_member_required
def inventario_asignar_cuadrilla(request):
    """Vista para asignar múltiples materiales del inventario global a una cuadrilla"""
    
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    if not es_admin:
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        cuadrilla_id = request.POST.get('cuadrilla')
        materiales_ids = request.POST.getlist('materiales_ids')
        cantidades = request.POST.getlist('cantidades')
        observacion = request.POST.get('observacion', '')
        
        # Validar que se seleccionó una cuadrilla
        if not cuadrilla_id:
            messages.error(request, 'Debes seleccionar una cuadrilla.')
            return redirect('inventario_asignar_cuadrilla')
        
        cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id, activo=True)
        
        # Validar que haya al menos un material seleccionado
        if not materiales_ids or len(materiales_ids) == 0:
            messages.error(request, 'Debes seleccionar al menos un material.')
            return redirect('inventario_asignar_cuadrilla')
        
        errores = []
        exitos = []
        
        with transaction.atomic():
            for i, material_id in enumerate(materiales_ids):
                if not material_id:
                    continue
                
                cantidad_str = cantidades[i] if i < len(cantidades) else '0'
                
                try:
                    cantidad = int(cantidad_str)
                    if cantidad <= 0:
                        continue
                except (ValueError, TypeError):
                    continue
                
                material = get_object_or_404(Material, id=material_id, activo=True)
                
                # Verificar stock global
                inv_global, created = InventarioGlobal.objects.get_or_create(material=material)
                
                if inv_global.cantidad < cantidad:
                    errores.append(f'❌ "{material.nombre}": Stock insuficiente. Solo hay {inv_global.cantidad} unidades.')
                    continue
                
                # Restar del inventario global
                inv_global.cantidad -= cantidad
                inv_global.actualizado_por = request.user
                inv_global.save()
                
                # Sumar al inventario de la cuadrilla
                inv_cuadrilla, created = InventarioCuadrilla.objects.get_or_create(
                    cuadrilla=cuadrilla,
                    material=material
                )
                inv_cuadrilla.cantidad += cantidad
                inv_cuadrilla.save()
                
                # Registrar movimiento
                MovimientoInventario.objects.create(
                    material=material,
                    tipo=MovimientoInventario.TipoMovimiento.SALIDA_A_CUADRILLA,
                    cantidad=cantidad,
                    cuadrilla=cuadrilla,
                    realizado_por=request.user,
                    observacion=observacion or f"Asignación de {cantidad} unidades a la cuadrilla {cuadrilla.nombre}"
                )
                
                exitos.append(f'✅ "{material.nombre}": {cantidad} unidades asignadas.')
        
        # Preparar mensaje para SweetAlert
        if errores and exitos:
            messages.warning(request, f'Asignación parcial.\n\n{chr(10).join(exitos)}\n\n{chr(10).join(errores)}')
        elif errores:
            messages.error(request, f'No se pudo completar la asignación.\n\n{chr(10).join(errores)}')
        elif exitos:
            messages.success(request, f'Asignación completada exitosamente.\n\n{chr(10).join(exitos)}')
        
        return redirect('inventario_todas_cuadrillas')
    
    # GET: Mostrar formulario
    cuadrillas = Cuadrilla.objects.filter(activo=True).order_by('nombre')
    materiales = Material.objects.filter(activo=True).order_by('nombre')
    
    # Obtener stock actual de cada material
    materiales_con_stock = []
    for material in materiales:
        inv_global, _ = InventarioGlobal.objects.get_or_create(material=material)
        materiales_con_stock.append({
            'id': material.id,
            'nombre': material.nombre,
            'stock': inv_global.cantidad
        })
    
    context = {
        'cuadrillas': cuadrillas,
        'materiales': materiales_con_stock,
    }
    return render(request, 'Inventario/inventario_asignar_cuadrilla.html', context)


@login_required
@staff_member_required
def inventario_cuadrilla_detalle(request, cuadrilla_id):
    """Vista para ver el inventario de una cuadrilla específica"""
    
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    if not es_admin:
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id, activo=True)
    
    # Obtener inventario de la cuadrilla
    inventario_cuadrilla = InventarioCuadrilla.objects.filter(
        cuadrilla=cuadrilla
    ).select_related('material').order_by('material__nombre')
    
    # Calcular total de materiales
    total_materiales = inventario_cuadrilla.count()
    total_unidades = sum(item.cantidad for item in inventario_cuadrilla)
    
    context = {
        'cuadrilla': cuadrilla,
        'inventario': inventario_cuadrilla,
        'total_materiales': total_materiales,
        'total_unidades': total_unidades,
    }
    return render(request, 'Inventario/inventario_cuadrilla_detalle.html', context)


@login_required
@staff_member_required
def inventario_devolver_cuadrilla(request, inventario_id):
    """Vista para devolver material de una cuadrilla al inventario global"""
    
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    if not es_admin:
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    inv_cuadrilla = get_object_or_404(InventarioCuadrilla, id=inventario_id)
    cuadrilla = inv_cuadrilla.cuadrilla
    material = inv_cuadrilla.material
    
    if request.method == 'POST':
        cantidad = request.POST.get('cantidad')
        observacion = request.POST.get('observacion', '')
        
        try:
            cantidad = int(cantidad)
            if cantidad <= 0:
                messages.error(request, 'La cantidad debe ser mayor a 0.')
                return redirect('inventario_cuadrilla_detalle', cuadrilla_id=cuadrilla.id)
            if cantidad > inv_cuadrilla.cantidad:
                messages.error(request, f'No se puede devolver más de lo que tiene la cuadrilla ({inv_cuadrilla.cantidad} unidades).')
                return redirect('inventario_cuadrilla_detalle', cuadrilla_id=cuadrilla.id)
        except ValueError:
            messages.error(request, 'La cantidad debe ser un número válido.')
            return redirect('inventario_cuadrilla_detalle', cuadrilla_id=cuadrilla.id)
        
        with transaction.atomic():
            # Restar de la cuadrilla
            inv_cuadrilla.cantidad -= cantidad
            inv_cuadrilla.save()
            
            # Sumar al inventario global
            inv_global, created = InventarioGlobal.objects.get_or_create(material=material)
            inv_global.cantidad += cantidad
            inv_global.actualizado_por = request.user
            inv_global.save()
            
            # Registrar movimiento
            MovimientoInventario.objects.create(
                material=material,
                tipo=MovimientoInventario.TipoMovimiento.DEVOLUCION_CUADRILLA,
                cantidad=cantidad,
                cuadrilla=cuadrilla,
                realizado_por=request.user,
                observacion=observacion or f"Devolución de {cantidad} unidades desde la cuadrilla {cuadrilla.nombre}"
            )
            
            # Si la cuadrilla quedó con 0, eliminar el registro (opcional)
            if inv_cuadrilla.cantidad == 0:
                inv_cuadrilla.delete()
        
        messages.success(request, f'✅ Se devolvieron {cantidad} unidades de "{material.nombre}" al inventario global.')
        return redirect('inventario_cuadrilla_detalle', cuadrilla_id=cuadrilla.id)
    
    context = {
        'inv_cuadrilla': inv_cuadrilla,
        'cuadrilla': cuadrilla,
        'material': material,
    }
    return render(request, 'Inventario/inventario_devolver_cuadrilla.html', context)


@login_required
@staff_member_required
def inventario_todas_cuadrillas(request):
    """Vista para ver el inventario de todas las cuadrillas"""
    
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    if not es_admin:
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Obtener todas las cuadrillas activas
    cuadrillas = Cuadrilla.objects.filter(activo=True).order_by('nombre')
    
    # Para cada cuadrilla, obtener su inventario
    inventario_por_cuadrilla = []
    for cuadrilla in cuadrillas:
        inventario = InventarioCuadrilla.objects.filter(
            cuadrilla=cuadrilla
        ).select_related('material')
        
        total_unidades = sum(item.cantidad for item in inventario)
        
        inventario_por_cuadrilla.append({
            'cuadrilla': cuadrilla,
            'inventario': inventario,
            'total_materiales': inventario.count(),
            'total_unidades': total_unidades,
        })
    
    context = {
        'inventario_por_cuadrilla': inventario_por_cuadrilla,
    }
    return render(request, 'Inventario/inventario_todas_cuadrillas.html', context)



@login_required
@staff_member_required
def panel_inventario(request):
    """Vista del panel de inventario con todas las opciones"""
    
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    if not es_admin:
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Estadísticas rápidas
    total_materiales = Material.objects.filter(activo=True).count()
    
    # Stock total en inventario global
    inventario_global = InventarioGlobal.objects.all()
    total_stock_global = sum(item.cantidad for item in inventario_global)
    materiales_bajo_stock = sum(1 for item in inventario_global if item.esta_bajo_stock)
    
    # Stock total en cuadrillas
    inventario_cuadrillas = InventarioCuadrilla.objects.all()
    total_stock_cuadrillas = sum(item.cantidad for item in inventario_cuadrillas)
    cuadrillas_con_materiales = inventario_cuadrillas.values('cuadrilla').distinct().count()
    
    # Últimos movimientos
    ultimos_movimientos = MovimientoInventario.objects.select_related(
        'material', 'cuadrilla', 'realizado_por'
    ).order_by('-fecha_movimiento')[:5]
    
    context = {
        'total_materiales': total_materiales,
        'total_stock_global': total_stock_global,
        'materiales_bajo_stock': materiales_bajo_stock,
        'total_stock_cuadrillas': total_stock_cuadrillas,
        'cuadrillas_con_materiales': cuadrillas_con_materiales,
        'ultimos_movimientos': ultimos_movimientos,
    }
    return render(request, 'Inventario/panel_inventario.html', context)


@login_required
@staff_member_required
def inventario_movimientos_cuadrilla(request, cuadrilla_id):
    """Vista para ver los movimientos de inventario de una cuadrilla específica"""
    
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    if not es_admin:
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_id, activo=True)
    
    # Filtros
    tipo_filtro = request.GET.get('tipo', '')
    material_filtro = request.GET.get('material', '')
    
    # Obtener movimientos de la cuadrilla
    movimientos = MovimientoInventario.objects.filter(
        cuadrilla=cuadrilla
    ).select_related('material', 'realizado_por', 'instalacion', 'soporte').order_by('-fecha_movimiento')
    
    if tipo_filtro:
        movimientos = movimientos.filter(tipo=tipo_filtro)
    
    if material_filtro:
        movimientos = movimientos.filter(material_id=material_filtro)
    
    # Paginación
    paginator = Paginator(movimientos, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    materiales = Material.objects.filter(activo=True).order_by('nombre')
    
    # Resumen de movimientos
    total_movimientos = movimientos.count()
    total_entradas = movimientos.filter(tipo='SALIDA_A_CUADRILLA').count()  # Lo que recibió del global
    total_gastos_instalacion = movimientos.filter(tipo='GASTO_INSTALACION').count()
    total_gastos_soporte = movimientos.filter(tipo='GASTO_SOPORTE').count()
    total_devoluciones = movimientos.filter(tipo='DEVOLUCION_CUADRILLA').count()
    
    # Resumen de cantidades
    total_recibido = sum(m.cantidad for m in movimientos.filter(tipo='SALIDA_A_CUADRILLA') if m.cantidad > 0)
    total_gastado_instalacion = sum(abs(m.cantidad) for m in movimientos.filter(tipo='GASTO_INSTALACION') if m.cantidad < 0)
    total_gastado_soporte = sum(abs(m.cantidad) for m in movimientos.filter(tipo='GASTO_SOPORTE') if m.cantidad < 0)
    total_devuelto = sum(m.cantidad for m in movimientos.filter(tipo='DEVOLUCION_CUADRILLA') if m.cantidad > 0)
    
    context = {
        'cuadrilla': cuadrilla,
        'movimientos': page_obj,
        'materiales': materiales,
        'tipos_movimiento': MovimientoInventario.TipoMovimiento.choices,
        'tipo_filtro': tipo_filtro,
        'material_filtro': material_filtro,
        'total_movimientos': total_movimientos,
        'total_entradas': total_entradas,
        'total_gastos_instalacion': total_gastos_instalacion,
        'total_gastos_soporte': total_gastos_soporte,
        'total_devoluciones': total_devoluciones,
        'total_recibido': total_recibido,
        'total_gastado_instalacion': total_gastado_instalacion,
        'total_gastado_soporte': total_gastado_soporte,
        'total_devuelto': total_devuelto,
        'stock_actual': total_recibido - total_gastado_instalacion - total_gastado_soporte - total_devuelto,
    }
    return render(request, 'Inventario/inventario_movimientos_cuadrilla.html', context)


@login_required
def mi_inventario(request):
    """Vista para que el instalador vea su inventario personal y gastos"""
    
    # Verificar permisos
    es_instalador = request.user.groups.filter(name='Instalador').exists()
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    
    if not (es_instalador or es_admin):
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Para admin: puede seleccionar cualquier cuadrilla
    cuadrilla_seleccionada = request.GET.get('cuadrilla_id')
    cuadrilla = None
    
    if es_admin and cuadrilla_seleccionada:
        cuadrilla = get_object_or_404(Cuadrilla, id=cuadrilla_seleccionada, activo=True)
    elif es_admin and not cuadrilla_seleccionada:
        # Admin sin selección - mostrar todas las cuadrillas disponibles
        cuadrillas_disponibles = Cuadrilla.objects.filter(activo=True).order_by('nombre')
        context = {
            'sin_cuadrilla': True,
            'es_admin': True,
            'cuadrillas_disponibles': cuadrillas_disponibles,
            'cuadrilla_seleccionada': '',
        }
        return render(request, 'Instaladores/mi_inventario.html', context)
    else:
        # Instalador normal - obtener su cuadrilla
        try:
            perfil = request.user.perfil
            cuadrilla = perfil.cuadrillas.filter(activo=True).first()
            if not cuadrilla:
                return render(request, 'Instaladores/mi_inventario.html', {'sin_cuadrilla': True, 'es_admin': False})
        except:
            return render(request, 'Instaladores/mi_inventario.html', {'sin_cuadrilla': True, 'es_admin': False})
    
    # ========== OBTENER INVENTARIO ACTUAL ==========
    inventario_actual = []
    inventario_dict = {}
    
    materiales_cuadrilla = InventarioCuadrilla.objects.filter(
        cuadrilla=cuadrilla
    ).select_related('material')
    
    total_unidades = 0
    for item in materiales_cuadrilla:
        inventario_actual.append({
            'material': item.material.nombre,
            'cantidad': item.cantidad,
            'material_obj': item.material
        })
        inventario_dict[item.material.nombre] = item.cantidad
        total_unidades += item.cantidad
    
    # Asegurar que todos los materiales base tengan valor
    materiales_base = ["Modem", "Conector", "Roseta", "Patch Cord", "Tensor", "Fibra Optica (metros)"]
    for material in materiales_base:
        if material not in inventario_dict:
            inventario_actual.append({
                'material': material,
                'cantidad': 0,
                'material_obj': None
            })
            inventario_dict[material] = 0
    
    # ========== RESUMEN DE GASTOS ==========
    total_recibido = sum(
        m.cantidad for m in MovimientoInventario.objects.filter(
            cuadrilla=cuadrilla, 
            tipo='SALIDA_A_CUADRILLA'
        ) if m.cantidad > 0
    )
    
    total_instalacion = sum(
        abs(m.cantidad) for m in MovimientoInventario.objects.filter(
            cuadrilla=cuadrilla, 
            tipo='GASTO_INSTALACION'
        ) if m.cantidad < 0
    )
    
    total_soporte = sum(
        abs(m.cantidad) for m in MovimientoInventario.objects.filter(
            cuadrilla=cuadrilla, 
            tipo='GASTO_SOPORTE'
        ) if m.cantidad < 0
    )
    
    total_devuelto = sum(
        m.cantidad for m in MovimientoInventario.objects.filter(
            cuadrilla=cuadrilla, 
            tipo='DEVOLUCION_CUADRILLA'
        ) if m.cantidad > 0
    )
    
    stock_actual = total_recibido - total_instalacion - total_soporte - total_devuelto
    
    # ========== MOVIMIENTOS CON PAGINACIÓN ==========
    movimientos_all = MovimientoInventario.objects.filter(
        cuadrilla=cuadrilla
    ).select_related('material', 'instalacion', 'soporte', 'realizado_por').order_by('-fecha_movimiento')
    
    paginator_mov = Paginator(movimientos_all, 15)
    page_mov = request.GET.get('page_movimientos', 1)
    movimientos_page = paginator_mov.get_page(page_mov)
    
    # ========== INSTALACIONES CON PAGINACIÓN ==========
    instalaciones_all = Instalacion.objects.filter(
        asignacion__cuadrilla=cuadrilla,
        completada=True
    ).select_related('asignacion', 'modelo_modem').order_by('-fecha_instalacion')
    
    paginator_inst = Paginator(instalaciones_all, 10)
    page_inst = request.GET.get('page_instalaciones', 1)
    instalaciones_page = paginator_inst.get_page(page_inst)
    
    # ========== SOPORTES CON PAGINACIÓN ==========
   # LÍNEA CORRECTA - elimina 'instalacion' que no existe
    soportes_all = Soporte.objects.filter(
        cuadrilla=cuadrilla
    ).select_related('asignacion', 'cuadrilla', 'modelo_modem').order_by('-fecha_creacion')
    
    paginator_sop = Paginator(soportes_all, 10)
    page_sop = request.GET.get('page_soportes', 1)
    soportes_page = paginator_sop.get_page(page_sop)
    
    # Cuadrillas disponibles para admin
    cuadrillas_disponibles = Cuadrilla.objects.filter(activo=True).order_by('nombre') if es_admin else []
    
    context = {
        'cuadrilla': cuadrilla,
        'inventario_actual': inventario_actual,
        'total_unidades': total_unidades,
        'movimientos_page': movimientos_page,
        'instalaciones_page': instalaciones_page,
        'soportes_page': soportes_page,
        'total_recibido': total_recibido,
        'total_instalacion': total_instalacion,
        'total_soporte': total_soporte,
        'total_devuelto': total_devuelto,
        'stock_actual': stock_actual,
        'sin_cuadrilla': False,
        'es_admin': es_admin,
        'cuadrillas_disponibles': cuadrillas_disponibles,
        'cuadrilla_seleccionada': cuadrilla.id if cuadrilla else '',
    }
    return render(request, 'Instaladores/mi_inventario.html', context)