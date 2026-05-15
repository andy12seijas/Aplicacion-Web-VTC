# tu_app/management/commands/corregir_fechas.py

from django.core.management.base import BaseCommand
from django.utils import timezone
import pytz

# IMPORTANTE: Cambia 'tu_app' por el nombre REAL de tu app
from myapp.models import (
    ContratoCliente, VentaDirecta, ClientePotencial, 
    Instalacion, Soporte, Ticket, ReportePago, 
    AsignacionContrato, MovimientoInventario, LeadInteresado,
    AsignacionSoporte
)


class Command(BaseCommand):
    help = 'Corrige las fechas guardadas con zona horaria incorrecta (EE.UU. -> Venezuela)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 INICIANDO CORRECCIÓN DE FECHAS...'))
        self.stdout.write('=' * 50)
        
        # Zonas horarias
        ve_tz = pytz.timezone('America/Caracas')
        us_tz = pytz.timezone('America/New_York')
        
        # Definir qué campos corregir en cada modelo
        modelos_a_corregir = [
            (ContratoCliente, ['fecha_creacion', 'fecha_actualizacion', 'fecha_completado']),
            (VentaDirecta, ['fecha_creacion', 'fecha_actualizacion']),
            (ClientePotencial, ['fecha_creacion', 'fecha_actualizacion']),
            (Instalacion, ['fecha_creacion', 'fecha_actualizacion', 'fecha_instalacion']),
            (Ticket, ['fecha_reporte', 'fecha_creacion', 'fecha_actualizacion', 'fecha_requerida']),
            (Soporte, ['fecha_creacion', 'fecha_actualizacion', 'fecha_inicio', 'fecha_fin', 'fecha_hora_servicio']),
            (AsignacionContrato, ['fecha_asignacion']),
            (AsignacionSoporte, ['fecha_asignacion']),
            (MovimientoInventario, ['fecha_movimiento']),
            (ReportePago, ['fecha_reporte', 'fecha_verificacion']),
            (LeadInteresado, ['fecha_creacion', 'fecha_contactado']),
        ]
        
        total_general = 0
        
        for modelo, campos in modelos_a_corregir:
            self.stdout.write(f'\n📦 Procesando {modelo.__name__}...')
            
            contador = 0
            total = modelo.objects.count()
            
            if total == 0:
                self.stdout.write(f'   ⏭️ Sin registros para procesar')
                continue
            
            for obj in modelo.objects.all():
                actualizado = False
                
                for campo in campos:
                    fecha = getattr(obj, campo)
                    if fecha:
                        try:
                            # Convertir fecha a zona horaria de Venezuela
                            if timezone.is_naive(fecha):
                                fecha_us = us_tz.localize(fecha)
                                fecha_ve = fecha_us.astimezone(ve_tz)
                            else:
                                fecha_ve = fecha.astimezone(ve_tz)
                            
                            setattr(obj, campo, fecha_ve)
                            actualizado = True
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f'   ⚠️ Error ID {obj.id} - {campo}: {e}'))
                
                if actualizado:
                    obj.save(update_fields=campos)
                    contador += 1
            
            total_general += contador
            self.stdout.write(self.style.SUCCESS(f'   ✅ {contador} de {total} registros corregidos'))
        
        self.stdout.write('=' * 50)
        self.stdout.write(self.style.SUCCESS(f'🎉 ¡CORRECCIÓN COMPLETADA! {total_general} registros actualizados'))