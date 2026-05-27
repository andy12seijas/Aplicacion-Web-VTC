import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import ContratoCliente, ClienteExterno, SoporteCliente
from .forms import ClienteExternoForm


def reportar_soporte(request):
    """Vista principal para reportar reclamos/soporte"""
    return render(request, 'pagos/reportar_soporte.html')


@csrf_exempt
@require_http_methods(["POST"])
def buscar_cliente_soporte(request):
    """Busca cliente por cédula y correo para soporte"""
    try:
        data = json.loads(request.body)
        cedula = data.get('cedula')
        
        
        # Buscar en ContratoCliente (clientes internos)
        contrato = ContratoCliente.objects.filter(
            cliente_potencial__cedula=cedula,
            
        ).select_related('cliente_potencial').first()
        
        if contrato:
            return JsonResponse({
                'exists': True,
                'cliente': {
                    'tipo': 'INTERNO',
                    'id': contrato.id,
                    'cedula': contrato.cedula,
                    'nombre_completo': contrato.nombre_completo,
                    'nombre': contrato.nombre,
                    'apellido': contrato.apellido,
                    'telefono': contrato.telefono_principal,
                    'correo': contrato.correo_electronico
                }
            })
        
        # Buscar en ClienteExterno
        cliente_externo = ClienteExterno.objects.filter(
            cedula=cedula,
        ).first()
        
        if cliente_externo:
            return JsonResponse({
                'exists': True,
                'cliente': {
                    'tipo': 'EXTERNO',
                    'id': cliente_externo.id,
                    'cedula': cliente_externo.cedula,
                    'nombre_completo': cliente_externo.nombre_completo,
                    'nombre': cliente_externo.nombre,
                    'apellido': cliente_externo.apellido,
                    'telefono': cliente_externo.telefono,
                    'correo': cliente_externo.correo
                }
            })
        
        return JsonResponse({'exists': False})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def registrar_cliente_externo_soporte(request):
    """Registra un nuevo cliente externo desde soporte"""
    try:
        form = ClienteExternoForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            return JsonResponse({
                'success': True,
                'cliente_id': cliente.id
            })
        else:
            return JsonResponse({
                'success': False,
                'error': dict(form.errors)
            }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def crear_soporte_cliente(request):
    """Crea un nuevo reclamo/soporte de cliente"""
    try:
        tipo_cliente = request.POST.get('tipo_cliente')
        reclamo = request.POST.get('reclamo')
        observacion = request.POST.get('observacion', '')
        foto = request.FILES.get('foto')
        
        # Validar reclamo
        if not reclamo:
            return JsonResponse({'error': 'Debes describir tu reclamo'}, status=400)
        
        # Crear soporte
        soporte = SoporteCliente(
            reclamo=reclamo,
            observacion=observacion,
            foto=foto,
            estado=SoporteCliente.EstadoSoporte.NO_LEIDO,
            tipo_cliente=tipo_cliente
        )
        
        # Asociar cliente
        if tipo_cliente == 'INTERNO':
            contrato_id = request.POST.get('contrato_id')
            soporte.contrato_id = contrato_id
        else:
            cliente_externo_id = request.POST.get('cliente_externo_id')
            soporte.cliente_externo_id = cliente_externo_id
        
        soporte.save()
        
        return JsonResponse({'success': True, 'soporte_id': soporte.id})
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)