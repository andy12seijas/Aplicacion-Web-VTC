# myapp/apps.py
from django.apps import AppConfig
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import os
import sys


class MyappConfig(AppConfig):  # Nombre de la clase = nombre app con mayúscula inicial
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'

    def ready(self):
        # Evitar que se ejecute dos veces en desarrollo
        if os.environ.get('RUN_MAIN') != 'true' and 'runserver' in sys.argv:
            return
        
        # Evitar que se ejecute en migraciones o comandos
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return
        
        self.start_scheduler()

    def start_scheduler(self):
        scheduler = BackgroundScheduler()
        
        # Programar la tarea para las 9 AM todos los días
        scheduler.add_job(
            self.actualizar_tasa,
            trigger=CronTrigger(hour=9, minute=0),
            id='actualizar_tasa_diaria',
            replace_existing=True
        )
        
        scheduler.start()
        print("📅 Scheduler de tasa de cambio iniciado - Se ejecutará a las 9:00 AM diario")

    def actualizar_tasa(self):
        """Función que actualiza la tasa en la base de datos"""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        try:
            call_command('actualizar_tasa', stdout=out)
            print(f"✅ {out.getvalue()}")
        except Exception as e:
            print(f"❌ Error al actualizar tasa: {str(e)}")