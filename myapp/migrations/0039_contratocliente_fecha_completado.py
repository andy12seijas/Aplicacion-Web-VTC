# Generated migration file
from django.db import migrations, models
from django.utils import timezone

def poblar_fecha_completado(apps, schema_editor):
    """
    Poblar fecha_completado para contratos existentes
    Usa fecha_actualizacion como aproximación
    """
    ContratoCliente = apps.get_model('myapp', 'ContratoCliente')
    
    # Para contratos ya completados, usar fecha_actualizacion
    # (asumiendo que cuando se completaron, esa fecha quedó registrada)
    contratos_completados = ContratoCliente.objects.filter(
        estado='COMPLETADO',
        fecha_completado__isnull=True
    )
    
    count = 0
    for contrato in contratos_completados:
        # Usar fecha_actualizacion como fecha de completado
        # No es perfecto, pero es lo mejor que tenemos
        contrato.fecha_completado = contrato.fecha_actualizacion
        contrato.save(update_fields=['fecha_completado'])
        count += 1
    
    print(f"✅ Actualizados {count} contratos completados con fecha_completado")

def reverse_poblar(apps, schema_editor):
    """En caso de revertir la migración"""
    ContratoCliente = apps.get_model('myapp', 'ContratoCliente')
    ContratoCliente.objects.all().update(fecha_completado=None)

class Migration(migrations.Migration):
    dependencies = [
        ('myapp', '0038_asignacioncontrato_trabajo_interno_and_more'),  # ← Cambia por tu última migración
    ]

    operations = [
        migrations.AddField(
            model_name='contratocliente',
            name='fecha_completado',
            field=models.DateTimeField(blank=True, help_text='Fecha y hora en que el contrato cambió a COMPLETADO por primera vez', null=True, verbose_name='Fecha de completado'),
        ),
        migrations.RunPython(poblar_fecha_completado, reverse_poblar),
    ]
