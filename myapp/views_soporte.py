# views.py
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse
from django.http import JsonResponse
from .models import InventarioCuadrilla, Material, ModeloModem, MovimientoInventario, Soporte, Ticket, AsignacionSoporte, Cuadrilla
from .forms import TicketConAsignacionForm, AsignacionSoporteForm, SoporteTecnicoForm, TicketForm
from django.core.files.storage import default_storage
def es_administrador(user):
    return user.is_staff or user.groups.filter(name='Administradores').exists()

@login_required
def gestion_soportes(request):
    """Vista principal de gestión de tickets de soporte"""
    
    # Obtener parámetros de filtro
    busqueda = request.GET.get('busqueda', '')
    filtro_cuadrilla = request.GET.get('cuadrilla', '')
    filtro_tipo = request.GET.get('tipo', '')
    tab_activa = request.GET.get('tab', 'en_proceso')
    
    # Obtener páginas
    page_en_proceso = request.GET.get('page_en_proceso', 1)
    page_completados = request.GET.get('page_completados', 1)
    
    # Verificar rol del usuario
    es_admin = request.user.is_staff or request.user.groups.filter(name='Administrador').exists()
    es_instalador = request.user.groups.filter(name='Instalador').exists()
    
    # Variables para el instalador
    cuadrilla_del_instalador_id = None
    cuadrilla_del_instalador_nombre = None
    
    # ============================================================
    # LÓGICA PARA INSTALADORES
    # ============================================================
    if es_instalador:
        # Obtener la cuadrilla del instalador
        try:
            perfil = request.user.perfil
            cuadrilla_del_instalador = perfil.cuadrillas.filter(activo=True).first()
            if cuadrilla_del_instalador:
                cuadrilla_del_instalador_id = cuadrilla_del_instalador.id
                cuadrilla_del_instalador_nombre = cuadrilla_del_instalador.nombre
                
                # Obtener SOLO tickets que tienen asignación activa con SU cuadrilla
                tickets_ids = AsignacionSoporte.objects.filter(
                    cuadrilla=cuadrilla_del_instalador,
                    activo=True
                ).values_list('ticket_id', flat=True)
                
                # CRÍTICO: Convertir a lista y verificar si existe
                tickets_ids_list = list(tickets_ids)
                
                if tickets_ids_list:
                    tickets_query = Ticket.objects.filter(id__in=tickets_ids_list)
                else:
                    # NO usar Ticket.objects.none() porque a veces falla
                    tickets_query = Ticket.objects.filter(id__in=[-1])  # IDs negativos no existen
            else:
                tickets_query = Ticket.objects.filter(id__in=[-1])
        except Exception as e:
            print(f"Error: {e}")
            tickets_query = Ticket.objects.filter(id__in=[-1])
    
    else:
        # Admin: ven todos los tickets
        tickets_query = Ticket.objects.all()
    
    # ============================================================
    # APLICAR FILTROS ADICIONALES
    # ============================================================
    
    if busqueda:
        tickets_query = tickets_query.filter(
            Q(ticket_padre__icontains=busqueda) |
            Q(nombre__icontains=busqueda) |
            Q(apellido__icontains=busqueda) |
            Q(cedula__icontains=busqueda) |
            Q(customer_id__icontains=busqueda) |
            Q(direccion__icontains=busqueda) |
            Q(telefono__icontains=busqueda)
        )
    
    if filtro_tipo:
        tickets_query = tickets_query.filter(tipo_soporte=filtro_tipo)
    
    if filtro_cuadrilla and es_admin:
        asignaciones = AsignacionSoporte.objects.filter(
            cuadrilla_id=filtro_cuadrilla,
            activo=True
        ).values_list('ticket_id', flat=True)
        tickets_query = tickets_query.filter(id__in=list(asignaciones))
    
    # ============================================================
    # SEPARAR POR ESTADO
    # ============================================================
    
    tickets_en_proceso = tickets_query.filter(
        ~Q(estado__in=['RESUELTO', 'CERRADO', 'CANCELADO'])
    ).order_by('-fecha_reporte')
    
    tickets_completados = tickets_query.filter(
        estado__in=['RESUELTO', 'CERRADO']
    ).order_by('-fecha_reporte')
    
    # ============================================================
    # PAGINACIÓN
    # ============================================================
    
    paginator_en_proceso = Paginator(tickets_en_proceso, 15)
    paginator_completados = Paginator(tickets_completados, 15)
    
    try:
        tickets_en_proceso_page = paginator_en_proceso.page(page_en_proceso)
    except (PageNotAnInteger, EmptyPage):
        tickets_en_proceso_page = paginator_en_proceso.page(1)
    
    try:
        tickets_completados_page = paginator_completados.page(page_completados)
    except (PageNotAnInteger, EmptyPage):
        tickets_completados_page = paginator_completados.page(1)
    
    # ============================================================
    # AGREGAR ASIGNACIONES A CADA TICKET
    # ============================================================
    
    for ticket in tickets_en_proceso_page:
        try:
            ticket.asignacion_actual = AsignacionSoporte.objects.filter(
                ticket=ticket, activo=True
            ).first()
            # Para instaladores, siempre puede registrar porque SOLO ve tickets de su cuadrilla
            if es_instalador:
                ticket.puede_registrar_soporte = True
            else:
                ticket.puede_registrar_soporte = False
        except:
            ticket.asignacion_actual = None
            ticket.puede_registrar_soporte = False
    
    for ticket in tickets_completados_page:
        try:
            ticket.asignacion_actual = AsignacionSoporte.objects.filter(
                ticket=ticket, activo=True
            ).first()
            if ticket.asignacion_actual:
                ticket.soporte = Soporte.objects.filter(asignacion=ticket.asignacion_actual).first()
            
            if es_instalador and ticket.soporte:
                ticket.participo = ticket.soporte.instaladores.filter(id=request.user.id).exists()
            else:
                ticket.participo = False
        except:
            ticket.asignacion_actual = None
            ticket.soporte = None
            ticket.participo = False
    
    # ============================================================
    # CONTEXTO
    # ============================================================
    
    cuadrillas = Cuadrilla.objects.filter(activo=True)
    
    context = {
        'tickets_en_proceso': tickets_en_proceso_page,
        'tickets_completados': tickets_completados_page,
        'cuadrillas': cuadrillas,
        'total_en_proceso': tickets_en_proceso.count(),
        'total_completados': tickets_completados.count(),
        'busqueda': busqueda,
        'filtro_cuadrilla': filtro_cuadrilla,
        'filtro_tipo': filtro_tipo,
        'tab_activa': tab_activa,
        'es_admin': es_admin,
        'es_instalador': es_instalador,
        'cuadrilla_del_instalador_id': cuadrilla_del_instalador_id,
        'cuadrilla_del_instalador_nombre': cuadrilla_del_instalador_nombre,
    }
    
    return render(request, 'Soporte/gestion_soportes.html', context)

@login_required
@user_passes_test(es_administrador)
def crear_ticket(request):
    """Crear un nuevo ticket de soporte"""
    
    if request.method == 'POST':
        form = TicketConAsignacionForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.creado_por = request.user
            ticket.save()
            
            # Crear asignación si se seleccionó una cuadrilla
            cuadrilla = form.cleaned_data.get('cuadrilla')
            if cuadrilla:
                asignacion = AsignacionSoporte.objects.create(
                    ticket=ticket,
                    cuadrilla=cuadrilla,
                    asignado_por=request.user,
                    observaciones=form.cleaned_data.get('observaciones_asignacion', '')
                )
                messages.success(request, f'Ticket #{ticket.ticket_padre} creado y asignado a {asignacion.cuadrilla.nombre}')
            else:
                messages.success(request, f'Ticket #{ticket.ticket_padre} creado exitosamente')
            
            return redirect('gestion_soportes')
    else:
        form = TicketConAsignacionForm()
    
    context = {
        'form': form,
        'titulo': 'Crear Nuevo Ticket',
        'action': 'Crear Ticket',
        'cuadrillas': Cuadrilla.objects.filter(activo=True),  # <-- LÍNEA IMPORTANTE
        'es_admin': request.user.is_staff or request.user.groups.filter(name='Administradores').exists(),
        'es_instalador': request.user.groups.filter(name='Instaladores').exists(),
    }
    
    return render(request, 'Soporte/form_ticket.html', context)


@login_required
@user_passes_test(es_administrador)
def editar_ticket(request, ticket_id):
    """Editar un ticket existente"""
    
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # Obtener parámetros de la URL para mantener la navegación
    tab = request.GET.get('tab', 'en_proceso')
    busqueda = request.GET.get('busqueda', '')
    filtro_cuadrilla = request.GET.get('cuadrilla', '')
    filtro_tipo = request.GET.get('tipo', '')
    
    if request.method == 'POST':
        form = TicketForm(request.POST, instance=ticket)
        
        # DEBUG: Imprimir errores en consola
        if not form.is_valid():
            print("=" * 50)
            print("ERRORES DEL FORMULARIO:")
            for field, errors in form.errors.items():
                print(f"  {field}: {', '.join(errors)}")
            print("=" * 50)
            
            # También mostrar errores como mensajes
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Error en {field}: {error}')
        else:
            form.save()
            messages.success(request, f'Ticket #{ticket.ticket_padre} actualizado exitosamente')
            
            # Construir URL de redirección
            redirect_url = reverse('gestion_soportes')
            params = []
            if tab:
                params.append(f'tab={tab}')
            if busqueda:
                params.append(f'busqueda={busqueda}')
            if filtro_cuadrilla:
                params.append(f'cuadrilla={filtro_cuadrilla}')
            if filtro_tipo:
                params.append(f'tipo={filtro_tipo}')
            
            if params:
                redirect_url += '?' + '&'.join(params)
            
            return redirect(redirect_url)
    else:
        form = TicketForm(instance=ticket)
    
    context = {
        'form': form,
        'titulo': f'Editar Ticket - {ticket.ticket_padre}',
        'action': 'Guardar Cambios',
        'ticket': ticket,
        'cuadrillas': Cuadrilla.objects.filter(activo=True),
        'es_admin': request.user.is_staff or request.user.groups.filter(name='Administradores').exists(),
        'es_instalador': request.user.groups.filter(name='Instaladores').exists(),
        'tab_actual': tab,
        'busqueda_actual': busqueda,
        'filtro_cuadrilla_actual': filtro_cuadrilla,
        'filtro_tipo_actual': filtro_tipo,
    }
    
    return render(request, 'Soporte/form_ticket.html', context)

@login_required
@user_passes_test(es_administrador)
def asignar_ticket(request, ticket_id):
    """Asignar un ticket a una cuadrilla"""
    
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # Verificar si ya tiene una asignación activa
    asignacion_existente = AsignacionSoporte.objects.filter(ticket=ticket, activo=True).first()
    if asignacion_existente:
        messages.warning(request, f'El ticket ya está asignado a {asignacion_existente.cuadrilla.nombre}')
        return redirect('gestion_soportes')
    
    if request.method == 'POST':
        form = AsignacionSoporteForm(request.POST)
        if form.is_valid():
            asignacion = form.save(commit=False)
            asignacion.ticket = ticket
            asignacion.asignado_por = request.user
            asignacion.save()
            messages.success(request, f'Ticket #{ticket.ticket_padre} asignado a {asignacion.cuadrilla.nombre}')
            return redirect('gestion_soportes')
    else:
        form = AsignacionSoporteForm()
    
    context = {
        'form': form,
        'ticket': ticket,
        'titulo': f'Asignar Ticket - {ticket.ticket_padre}',
        'action': 'Asignar'
    }
    
    return render(request, 'Soporte/asignar_ticket.html', context)


@login_required
@user_passes_test(es_administrador)
def desasignar_ticket(request, asignacion_id):
    """Desasignar un ticket (eliminar la asignación)"""
    
    if request.method == 'POST':
        asignacion = get_object_or_404(AsignacionSoporte, id=asignacion_id, activo=True)
        ticket = asignacion.ticket
        
        # Verificar si ya tiene un soporte técnico asociado
        soporte_existente = Soporte.objects.filter(asignacion=asignacion).first()
        if soporte_existente:
            messages.error(request, 'No se puede desasignar porque ya se ha registrado el soporte técnico')
            return redirect('gestion_soportes')
        
        asignacion.activo = False
        asignacion.save()
        
        # Si el ticket estaba en ASIGNADO, volver a PENDIENTE
        if ticket.estado == 'ASIGNADO':
            ticket.estado = 'PENDIENTE'
            asignacion.delete()
            ticket.save()
        
        messages.success(request, f'Ticket #{ticket.ticket_padre} desasignado exitosamente')
    
    return redirect('gestion_soportes')


@login_required
def registrar_soporte(request, ticket_id):
    """Registrar la ejecución del soporte técnico (con inventario)"""
    
    # Verificar permisos
    es_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    es_instalador = request.user.groups.filter(name='Instalador').exists()
    
    if not (es_admin or es_instalador):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'No tienes permisos para acceder a esta página.'}, status=403)
        messages.error(request, 'No tienes permisos para acceder a esta página.')
        return redirect('dashboard')
    
    # Obtener el ticket
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # Verificar que tenga asignación activa
    asignacion = AsignacionSoporte.objects.filter(ticket=ticket, activo=True).first()
    if not asignacion:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'El ticket no tiene una asignación activa.'}, status=400)
        messages.error(request, 'El ticket no tiene una asignación activa.')
        return redirect('gestion_soportes')
    
    # Obtener la cuadrilla
    cuadrilla = asignacion.cuadrilla
    
    # Verificar permisos de instalador
    if es_instalador and not es_admin:
        perfil = request.user.perfil
        cuadrillas_ids = perfil.cuadrillas.filter(activo=True).values_list('id', flat=True)
        
        if cuadrilla.id not in cuadrillas_ids:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'No tienes permiso para registrar soporte en este ticket.'}, status=403)
            messages.error(request, 'No tienes permiso para registrar soporte en este ticket.')
            return redirect('gestion_soportes')
    
    # Verificar si ya existe un soporte técnico
    soporte, created = Soporte.objects.get_or_create(
        asignacion=asignacion,
        defaults={
            'cuadrilla': cuadrilla,
            'estado': Soporte.EstadoEjecucion.PENDIENTE
        }
    )
    
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
    inventario_cuadrilla_template = {
        "Modem": inventario_cuadrilla_raw.get("Modem", 0),
        "Conector": inventario_cuadrilla_raw.get("Conector", 0),
        "Roseta": inventario_cuadrilla_raw.get("Roseta", 0),
        "Patch_Cord": inventario_cuadrilla_raw.get("Patch Cord", 0),
        "Tensor": inventario_cuadrilla_raw.get("Tensor", 0),
        "metros": inventario_cuadrilla_raw.get("Fibra Optica (metros)", 0),
        "Tirros": inventario_cuadrilla_raw.get("Tirros", 0),
    }
    
    # Obtener los instaladores de la cuadrilla
    instaladores_de_cuadrilla = [perfil.usuario for perfil in cuadrilla.instaladores.all()]
    
    # Verificar si es petición AJAX
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Obtener fotos existentes
    fotos_existentes = json.dumps(soporte.fotos or []) if soporte.fotos else '[]'
    
    if request.method == 'POST':
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
        sn_modem = request.POST.get('sn_modem', '').strip()
        mac_modem = request.POST.get('mac_modem', '').strip()
        modem_viejo = request.POST.get('modem_viejo','').strip()
        sn_modem_viejo = request.POST.get('sn_modem_viejo','').strip()
        mac_modem_viejo = request.POST.get('mac_modem_viejo','').strip()
        # Fechas y datos del servicio
        fecha_hora_servicio = request.POST.get('fecha_hora_servicio')
        falla_encontrada = request.POST.get('falla_encontrada', '').strip()
        solucion = request.POST.get('solucion', '').strip()
        caja_nap_utilizada = request.POST.get('caja_nap_utilizada', '').strip()
        puerto_nap_utilizado = request.POST.get('puerto_nap_utilizado', '').strip()
        pin_lat = request.POST.get('pin_ubicacion_lat', '').strip()
        pin_lng = request.POST.get('pin_ubicacion_lng', '').strip()
        estado = request.POST.get('estado', Soporte.EstadoEjecucion.PENDIENTE)
        observaciones = request.POST.get('observaciones', '').strip()
        
        # Instaladores
        instaladores_ids = request.POST.get('instaladores', '')
        instaladores_list = [int(id) for id in instaladores_ids.split(',') if id.strip().isdigit()] if instaladores_ids else []
        
        # ========== VALIDAR STOCK (MISMA LÓGICA QUE REALIZAR INSTALACION) ==========
        errores_stock = []
        
        # Validar módem - solo si se seleccionó
        if modelo_modem_id and modelo_modem_id != '' and modelo_modem_id != 'None':
            # Verificar si se completó serial o MAC (para saber si realmente se usó)
            if sn_modem or mac_modem:
                if inventario_cuadrilla_template.get("Modem", 0) < 1:
                    errores_stock.append("No hay módems disponibles en el inventario de la cuadrilla.")
        
        # Validar conectores (incluyendo malos)
        if conectores_totales > 0:
            if conectores_totales > inventario_cuadrilla_template.get("Conector", 0):
                errores_stock.append(f"Stock insuficiente de conectores. Necesitas {conectores_totales} (Buenos: {conectores_usados}, Malos: {conectores_malos_usados}). Disponible: {inventario_cuadrilla_template.get('Conector', 0)}")
        
        # Validar rosetas
        if rosetas_usadas > 0:
            if rosetas_usadas > inventario_cuadrilla_template.get("Roseta", 0):
                errores_stock.append(f"Stock insuficiente de rosetas. Disponible: {inventario_cuadrilla_template.get('Roseta', 0)}")
        
        # Validar patch cord
        if patch_usados > 0:
            if patch_usados > inventario_cuadrilla_template.get("Patch_Cord", 0):
                errores_stock.append(f"Stock insuficiente de patch cord. Disponible: {inventario_cuadrilla_template.get('Patch_Cord', 0)}")
        
        # Validar tensores
        if tensores_usados > 0:
            if tensores_usados > inventario_cuadrilla_template.get("Tensor", 0):
                errores_stock.append(f"Stock insuficiente de tensores. Disponible: {inventario_cuadrilla_template.get('Tensor', 0)}")
        
        # Validar tirros
        if tirros_usados > 0:
            if tirros_usados > inventario_cuadrilla_template.get("Tirros", 0):
                errores_stock.append(f"Stock insuficiente de tirros. Disponible: {inventario_cuadrilla_template.get('Tirros', 0)}")
        
        # Validar fibra
        if metros_usados > 0:
            if metros_usados > inventario_cuadrilla_template.get("metros", 0):
                errores_stock.append(f"Stock insuficiente de fibra óptica. Metros disponibles: {inventario_cuadrilla_template.get('metros', 0)}")
        
        # Si hay errores de stock, mostrar mensajes
        if errores_stock:
            if is_ajax:
                return JsonResponse({'error': '<br>'.join(errores_stock)}, status=400)
            for error in errores_stock:
                messages.error(request, f'❌ {error}')
            return redirect('registrar_soporte', ticket_id=ticket.id)
        
        # ========== VALIDACIÓN ADICIONAL CON BD ==========
        # Validar módem en BD
        modem_usado = False
        if modelo_modem_id and modelo_modem_id != '' and modelo_modem_id != 'None':
            if sn_modem or mac_modem:
                modem_usado = True
                inv_modem_bd = InventarioCuadrilla.objects.filter(cuadrilla=cuadrilla, material__nombre="Modem").first()
                if not inv_modem_bd or inv_modem_bd.cantidad < 1:
                    if is_ajax:
                        return JsonResponse({'error': 'No hay módems disponibles en inventario'}, status=400)
                    messages.error(request, 'No hay módems disponibles en inventario')
                    return redirect('registrar_soporte', ticket_id=ticket.id)
        
        # Validar conectores en BD
        if conectores_totales > 0:
            inv_conector_bd = InventarioCuadrilla.objects.filter(cuadrilla=cuadrilla, material__nombre="Conector").first()
            if not inv_conector_bd or inv_conector_bd.cantidad < conectores_totales:
                if is_ajax:
                    return JsonResponse({'error': f'Stock insuficiente de conectores. Necesitas {conectores_totales}. Disponible: {inv_conector_bd.cantidad if inv_conector_bd else 0}'}, status=400)
                messages.error(request, f'Stock insuficiente de conectores. Necesitas {conectores_totales}. Disponible: {inv_conector_bd.cantidad if inv_conector_bd else 0}')
                return redirect('registrar_soporte', ticket_id=ticket.id)
        
        # Validar fibra en BD
        if metros_usados > 0:
            inv_fibra_bd = InventarioCuadrilla.objects.filter(cuadrilla=cuadrilla, material__nombre="Fibra Optica (metros)").first()
            if not inv_fibra_bd or inv_fibra_bd.cantidad < metros_usados:
                if is_ajax:
                    return JsonResponse({'error': f'Stock insuficiente de fibra. Disponible: {inv_fibra_bd.cantidad if inv_fibra_bd else 0}'}, status=400)
                messages.error(request, f'Stock insuficiente de fibra. Disponible: {inv_fibra_bd.cantidad if inv_fibra_bd else 0}')
                return redirect('registrar_soporte', ticket_id=ticket.id)
        
        # Validar patch cord en BD
        if patch_usados > 0:
            inv_patch_bd = InventarioCuadrilla.objects.filter(cuadrilla=cuadrilla, material__nombre="Patch Cord").first()
            if not inv_patch_bd or inv_patch_bd.cantidad < patch_usados:
                if is_ajax:
                    return JsonResponse({'error': f'Stock insuficiente de patch cord. Disponible: {inv_patch_bd.cantidad if inv_patch_bd else 0}'}, status=400)
                messages.error(request, f'Stock insuficiente de patch cord. Disponible: {inv_patch_bd.cantidad if inv_patch_bd else 0}')
                return redirect('registrar_soporte', ticket_id=ticket.id)
        
        # ========== GUARDAR SOPORTE ==========
        try:
            soporte.fecha_hora_servicio = fecha_hora_servicio if fecha_hora_servicio else None
            soporte.falla_encontrada = falla_encontrada if falla_encontrada else None
            soporte.solucion = solucion if solucion else None
            
            # Modelo modem - guardar SOLO si se usó
            if modem_usado:
                try:
                    soporte.modelo_modem_id = int(modelo_modem_id)
                except (ValueError, TypeError):
                    soporte.modelo_modem = None
            else:
                soporte.modelo_modem = None
            
            soporte.sn_modem = sn_modem if sn_modem else None
            soporte.mac_modem = mac_modem if mac_modem else None
            
            # Materiales
            soporte.inicio_fibra = inicio_fibra if inicio_fibra > 0 else None
            soporte.final_fibra = final_fibra if final_fibra > 0 else None
            soporte.conectores = conectores_usados if conectores_usados > 0 else 0
            soporte.rosetas = rosetas_usadas if rosetas_usadas > 0 else 0
            soporte.patch_cord = patch_usados if patch_usados > 0 else 0
            soporte.tensores = tensores_usados if tensores_usados > 0 else 0
            soporte.conectores_malos = conectores_malos_usados if conectores_malos_usados > 0 else 0
            soporte.tirros = tirros_usados if tirros_usados > 0 else 0
            
            # Datos NAP
            soporte.caja_nap_utilizada = caja_nap_utilizada if caja_nap_utilizada else None
            soporte.puerto_nap_utilizado = puerto_nap_utilizado if puerto_nap_utilizado else None
            
            # Ubicación PIN
            if pin_lat:
                try:
                    soporte.pin_ubicacion_lat = float(pin_lat)
                except (ValueError, TypeError):
                    soporte.pin_ubicacion_lat = None
            if pin_lng:
                try:
                    soporte.pin_ubicacion_lng = float(pin_lng)
                except (ValueError, TypeError):
                    soporte.pin_ubicacion_lng = None
            
            soporte.estado = estado
            soporte.observaciones = observaciones if observaciones else None
            
            # Determinar estado final del ticket
            if fecha_hora_servicio and falla_encontrada and solucion:
                soporte.estado = 'COMPLETADO'
                ticket.estado = 'RESUELTO'
            else:
                soporte.estado = 'EN_PROCESO'
                ticket.estado = 'EN_PROCESO'
            
            # Procesar fotos
            fotos_subidas = request.FILES.getlist('fotos')
            fotos_urls = []
            
            for foto in fotos_subidas:
                if not foto.content_type.startswith('image/'):
                    if is_ajax:
                        return JsonResponse({'error': f'El archivo {foto.name} no es una imagen válida.'}, status=400)
                    messages.error(request, f'El archivo {foto.name} no es una imagen válida.')
                    return redirect('registrar_soporte', ticket_id=ticket.id)
                
                if foto.size > 5 * 1024 * 1024:
                    if is_ajax:
                        return JsonResponse({'error': f'El archivo {foto.name} excede el tamaño máximo de 5MB.'}, status=400)
                    messages.error(request, f'El archivo {foto.name} excede el tamaño máximo de 5MB.')
                    return redirect('registrar_soporte', ticket_id=ticket.id)
                
                timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                filename = f'soportes/soporte_{soporte.id}_{timestamp}_{foto.name}'
                saved_path = default_storage.save(filename, foto)
                fotos_urls.append(default_storage.url(saved_path))
            
            fotos_actuales = soporte.fotos or []
            fotos_actuales.extend(fotos_urls)
            soporte.fotos = fotos_actuales
            soporte.modem_viejo=modem_viejo if modem_viejo else None
            soporte.sn_modem_viejo=sn_modem_viejo if sn_modem_viejo else None
            soporte.mac_modem_viejo=mac_modem_viejo if mac_modem_viejo else None
            soporte.save()
            
            # ========== GUARDAR INSTALADORES ==========
            if instaladores_list:
                soporte.instaladores.set(instaladores_list)
            else:
                usuarios_instaladores = [perfil.usuario for perfil in cuadrilla.instaladores.all()]
                if usuarios_instaladores:
                    soporte.instaladores.set(usuarios_instaladores)
                else:
                    soporte.instaladores.add(request.user)
            
            # ========== RESTAR MATERIALES DEL INVENTARIO ==========
            from django.db import transaction
            
            with transaction.atomic():
                # Restar módem
                if modem_usado:
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
                            observacion=f"Soporte #{soporte.id} - Módem usado (SN: {sn_modem or 'N/A'}, MAC: {mac_modem or 'N/A'})"
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
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                            cantidad=-conectores_usados,
                            cuadrilla=cuadrilla,
                            soporte=soporte,
                            realizado_por=request.user,
                            observacion=f"Soporte #{soporte.id} - {conectores_usados} conectores BUENOS usados"
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
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                            cantidad=-conectores_malos_usados,
                            cuadrilla=cuadrilla,
                            soporte=soporte,
                            realizado_por=request.user,
                            observacion=f"Soporte #{soporte.id} - {conectores_malos_usados} conectores MALOS usados"
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
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                            cantidad=-rosetas_usadas,
                            cuadrilla=cuadrilla,
                            soporte=soporte,
                            realizado_por=request.user,
                            observacion=f"Soporte #{soporte.id} - {rosetas_usadas} rosetas usadas"
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
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                            cantidad=-patch_usados,
                            cuadrilla=cuadrilla,
                            soporte=soporte,
                            realizado_por=request.user,
                            observacion=f"Soporte #{soporte.id} - {patch_usados} patch cord usados"
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
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                            cantidad=-tensores_usados,
                            cuadrilla=cuadrilla,
                            soporte=soporte,
                            realizado_por=request.user,
                            observacion=f"Soporte #{soporte.id} - {tensores_usados} tensores usados"
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
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                            cantidad=-tirros_usados,
                            cuadrilla=cuadrilla,
                            soporte=soporte,
                            realizado_por=request.user,
                            observacion=f"Soporte #{soporte.id} - {tirros_usados} tirros usados"
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
                            tipo=MovimientoInventario.TipoMovimiento.GASTO_SOPORTE,
                            cantidad=-metros_usados,
                            cuadrilla=cuadrilla,
                            soporte=soporte,
                            realizado_por=request.user,
                            observacion=f"Soporte #{soporte.id} - {metros_usados} metros de fibra usados"
                        )
            
            # Guardar cambios en el ticket
            ticket.save()
            
            mensaje = '✅ Soporte técnico registrado exitosamente.'
            
            if is_ajax:
                return JsonResponse({'success': True, 'message': mensaje})
            
            messages.success(request, mensaje)
            return redirect('gestion_soportes')
            
        except Exception as e:
            if is_ajax:
                return JsonResponse({'error': f'Error al guardar: {str(e)}'}, status=400)
            messages.error(request, f'Error al guardar: {str(e)}')
            return redirect('registrar_soporte', ticket_id=ticket.id)
    
    # ========== GET: Mostrar formulario ==========
    form = SoporteTecnicoForm(instance=soporte)
    modelos_modem = ModeloModem.objects.filter(activo=True).order_by('nombre')
    
    # Obtener valores actuales para el resumen
    valores_actuales = {
        'inicio_fibra': soporte.inicio_fibra or 0,
        'final_fibra': soporte.final_fibra or 0,
        'conectores': soporte.conectores or 0,
        'conectores_malos': soporte.conectores_malos or 0,
        'rosetas': soporte.rosetas or 0,
        'patch_cord': soporte.patch_cord or 0,
        'tensores': soporte.tensores or 0,
        'tirros': soporte.tirros or 0,
    }
    
    instaladores_seleccionados = list(soporte.instaladores.values_list('id', flat=True))
    
    context = {
        'form': form,
        'ticket': ticket,
        'asignacion': asignacion,
        'soporte': soporte,
        'cuadrilla': cuadrilla,
        'modelos_modem': modelos_modem,
        'instaladores_disponibles': instaladores_de_cuadrilla,
        'instaladores_seleccionados': instaladores_seleccionados,
        'inventario_cuadrilla': inventario_cuadrilla_template,
        'fotos_existentes': fotos_existentes,
        'valores_actuales': valores_actuales,
        'titulo': f'Registrar Soporte - {ticket.ticket_padre}',
        'action': 'Guardar Soporte',
        'es_admin': es_admin,
    }
    
    return render(request, 'Soporte/form_soporte.html', context)


@login_required
def ver_detalle_soporte(request, ticket_id):
    """Ver detalle completo del ticket y su soporte (modo modal)"""
    
    ticket = get_object_or_404(Ticket, id=ticket_id)
    asignacion = AsignacionSoporte.objects.filter(ticket=ticket, activo=True).first()
    soporte = None
    
    if asignacion:
        soporte = Soporte.objects.filter(asignacion=asignacion).first()
    
    data = {
        'ticket': {
            'id': ticket.id,
            'ticket_padre': ticket.ticket_padre,
            'tipo_soporte': ticket.get_tipo_soporte_display(),
            'nombre_completo': ticket.nombre_completo,
            'cedula': ticket.cedula,
            'customer_id': ticket.customer_id,
            'telefono': ticket.telefono,
            
            'direccion': ticket.direccion,
            'plan': ticket.plan.nombre if ticket.plan else 'N/A',
            'falla': ticket.falla,
           
            'estado': ticket.get_estado_display(),
            'fecha_reporte': ticket.fecha_reporte.strftime('%d/%m/%Y %H:%M') if ticket.fecha_reporte else 'N/A',
            'fecha_requerida': ticket.fecha_requerida.strftime('%d/%m/%Y %H:%M') if ticket.fecha_requerida else 'N/A',
            'observaciones': ticket.observaciones,
            'creado_por': ticket.creado_por.get_full_name() or ticket.creado_por.username if ticket.creado_por else 'Sistema',
            'fecha_creacion': ticket.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        },
        'asignacion': {
            'cuadrilla': asignacion.cuadrilla.nombre if asignacion else None,
            'cuadrilla_estado': asignacion.cuadrilla.get_estado_display() if asignacion else None,
            'fecha_asignacion': asignacion.fecha_asignacion.strftime('%d/%m/%Y %H:%M') if asignacion else None,
            'observaciones': asignacion.observaciones if asignacion else None,
        },
        'soporte': {
            'existe': soporte is not None,
            'estado': soporte.get_estado_display() if soporte else None,
            'fecha_hora_servicio': soporte.fecha_hora_servicio.strftime('%d/%m/%Y %H:%M') if soporte and soporte.fecha_hora_servicio else None,
            'falla_encontrada': soporte.falla_encontrada if soporte else None,
            'solucion': soporte.solucion if soporte else None,
            'modelo_modem': soporte.modelo_modem.nombre if soporte and soporte.modelo_modem else None,
            'sn_modem': soporte.sn_modem if soporte else None,
            'mac_modem': soporte.mac_modem if soporte else None,
            'metros_utilizados': soporte.metros_utilizados if soporte else 0,
            'conectores': soporte.conectores if soporte else 0,
            'rosetas': soporte.rosetas if soporte else 0,
            'patch_cord': soporte.patch_cord if soporte else 0,
            'tensores': soporte.tensores if soporte else 0,
            'conectores_malos': soporte.conectores_malos if soporte else 0,
            'tirros': soporte.tirros if soporte else 0,
            'caja_nap_utilizada': soporte.caja_nap_utilizada if soporte else None,
            'puerto_nap_utilizado': soporte.puerto_nap_utilizado if soporte else None,
            'pin_ubicacion': soporte.pin_ubicacion if soporte else None,
            'fotos': soporte.fotos if soporte else [],
            'observaciones': soporte.observaciones if soporte else None,
            'instaladores': [inst.get_full_name() or inst.username for inst in soporte.instaladores.all()] if soporte else [],
            'fecha_inicio': soporte.fecha_inicio.strftime('%d/%m/%Y %H:%M') if soporte and soporte.fecha_inicio else None,
            'fecha_fin': soporte.fecha_fin.strftime('%d/%m/%Y %H:%M') if soporte and soporte.fecha_fin else None,
        }
    }
    
    return JsonResponse(data)


@login_required
@user_passes_test(es_administrador)
def crear_ticket_rapido(request):
    """Crear ticket automáticamente desde texto formateado"""
    
    if request.method == 'POST':
        import json
        import re
        from .models import Plan, Cuadrilla, AsignacionSoporte, Ticket
        
        datos_json = request.POST.get('datos_json', '{}')
        cuadrilla_id = request.POST.get('cuadrilla_id')
        observaciones_asignacion = request.POST.get('observaciones_asignacion', '')
        
        try:
            datos = json.loads(datos_json)
        except:
            messages.error(request, 'Error al procesar los datos')
            return redirect('gestion_soportes')
        
        # Separar nombre y apellido correctamente
        nombre_completo = datos.get('nombre_completo', '')
        if nombre_completo:
            partes = nombre_completo.strip().split()
            if len(partes) == 1:
                nombre = partes[0]
                apellido = ''
            elif len(partes) == 2:
                nombre = partes[0]
                apellido = partes[1]
            else:
                nombre = ' '.join(partes[:-2])
                apellido = ' '.join(partes[-2:])
        else:
            nombre = datos.get('nombre', '')
            apellido = datos.get('apellido', '')
        
        # Limpiar cédula - eliminar V-, E-, etc. dejar solo números
        cedula_raw = datos.get('cedula', '')
        cedula_limpia = re.sub(r'[^0-9]', '', cedula_raw)
        
        # Limpiar teléfono - dejar solo números
        telefono_raw = datos.get('telefono', '')
        telefono_limpio = re.sub(r'[^0-9]', '', telefono_raw)
        
        # Buscar el plan
        plan_nombre = datos.get('plan', '')
        plan = None
        if plan_nombre:
            numeros = re.findall(r'\d+', str(plan_nombre))
            if numeros:
                plan = Plan.objects.filter(nombre__icontains=numeros[0]).first()
        
        if not plan:
            plan = Plan.objects.filter(activo=True).first()
        
        # Crear ticket
        ticket = Ticket.objects.create(
            ticket_padre=datos.get('ticket_padre', ''),
            tipo_soporte=datos.get('tipo', 'SOPORTE'),
            nombre=nombre,
            apellido=apellido,
            cedula=cedula_limpia,  # Cédula limpia (solo números)
            customer_id=datos.get('customer_id', ''),
            telefono=telefono_limpio,  # Teléfono limpio (solo números)
            direccion=datos.get('direccion', ''),
            plan=plan,
            falla=datos.get('falla', ''),
            creado_por=request.user
        )
        
        # Asignar a cuadrilla si se seleccionó
        if cuadrilla_id and cuadrilla_id != '':
            try:
                cuadrilla = Cuadrilla.objects.get(id=cuadrilla_id, activo=True)
                AsignacionSoporte.objects.create(
                    ticket=ticket,
                    cuadrilla=cuadrilla,
                    asignado_por=request.user,
                    observaciones=observaciones_asignacion
                )
                messages.success(request, f'Ticket #{ticket.ticket_padre} creado y asignado a {cuadrilla.nombre}')
            except Cuadrilla.DoesNotExist:
                messages.success(request, f'Ticket #{ticket.ticket_padre} creado exitosamente')
        else:
            messages.success(request, f'Ticket #{ticket.ticket_padre} creado exitosamente')
        
        return redirect('gestion_soportes')
    
    return redirect('gestion_soportes')