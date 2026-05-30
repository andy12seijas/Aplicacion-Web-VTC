# myapp/management/commands/actualizar_tasa.py
import datetime
from django.core.management.base import BaseCommand
from bcv_exchange import get_exchange_rate  # ← Cambio aquí
from myapp.models import TasaCambio


class Command(BaseCommand):
    help = 'Actualiza la tasa de cambio del dólar desde el BCV'

    def handle(self, *args, **options):
        try:
            # Obtener la tasa del BCV con bcv-exchange
            exchange_data = get_exchange_rate()
            tasa_usd = exchange_data['exchange_rates']['USD']
            
            if not tasa_usd:
                self.stdout.write(self.style.ERROR('No se pudo obtener la tasa'))
                return
            
            # Guardar en la base de datos
            TasaCambio.objects.create(
                tasa=tasa_usd,
                fecha=datetime.date.today(),
                activo=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(f' Tasa guardada: 1 USD = {tasa_usd} Bs')
            )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f' Error: {str(e)}'))