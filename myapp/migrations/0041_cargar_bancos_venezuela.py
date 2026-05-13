# migrations/XXXX_cargar_bancos_venezuela.py
from django.db import migrations

def crear_bancos_venezuela(apps, schema_editor):
    Banco = apps.get_model('myapp', 'Banco')
    
    # Primero eliminar todos los bancos existentes
    Banco.objects.all().delete()
    
    bancos = [
        # Bancos de Venezuela según la lista proporcionada
        {'codigo': '0102', 'nombre': 'Banco de Venezuela S.A.', 'activo': True},
        {'codigo': '0105', 'nombre': 'Mercantil Banco', 'activo': True},
        {'codigo': '0134', 'nombre': 'Banesco Banco Universal', 'activo': True},
        {'codigo': '0108', 'nombre': 'BBVA Provincial', 'activo': True},
        {'codigo': '0191', 'nombre': 'Banco Nacional de Crédito (BNC)', 'activo': True},
        {'codigo': '0172', 'nombre': 'Bancamiga Banco Universal', 'activo': True},
        {'codigo': '0163', 'nombre': 'Banco del Tesoro', 'activo': True},
        {'codigo': '0114', 'nombre': 'Bancaribe', 'activo': True},
        {'codigo': '0175', 'nombre': 'Banco Digital de los Trabajadores (Antiguo Bicentenario)', 'activo': True},
        {'codigo': '0104', 'nombre': 'Banco Venezolano de Crédito', 'activo': True},
        {'codigo': '0115', 'nombre': 'Banco Exterior', 'activo': True},
        {'codigo': '0151', 'nombre': 'BFC Banco Fondo Común', 'activo': True},
        {'codigo': '0174', 'nombre': 'Banplus Banco Universal', 'activo': True},
        {'codigo': '0138', 'nombre': 'Banco Plaza', 'activo': True},
        {'codigo': '0157', 'nombre': 'DelSur Banco Universal', 'activo': True},
        {'codigo': '0128', 'nombre': 'Banco Caroní', 'activo': True},
        {'codigo': '0171', 'nombre': 'Banco Activo', 'activo': True},
        {'codigo': '0156', 'nombre': '100% Banco', 'activo': True},
        {'codigo': '0166', 'nombre': 'Banco Agrícola de Venezuela', 'activo': True},
        {'codigo': '0177', 'nombre': 'BANFANB', 'activo': True},
        {'codigo': '0137', 'nombre': 'Banco Sofitasa', 'activo': True},
        {'codigo': '0168', 'nombre': 'Bancrecer', 'activo': True},
        {'codigo': '0169', 'nombre': 'Mi Banco (R4 Banco Microfinanciero)', 'activo': True},
        {'codigo': '0178', 'nombre': 'N58 Banco Digital', 'activo': True},
        {'codigo': '0146', 'nombre': 'Bangente', 'activo': True},
        {'codigo': '0173', 'nombre': 'Banco Internacional de Desarrollo', 'activo': True},
    ]
    
    for banco in bancos:
        banco_obj, created = Banco.objects.get_or_create(
            codigo=banco['codigo'],
            defaults={
                'nombre': banco['nombre'],
                'activo': banco['activo']
            }
        )
        if created:
            print(f"✅ Creado: {banco['nombre']} ({banco['codigo']})")
        else:
            # Actualizar si es necesario
            if banco_obj.nombre != banco['nombre'] or banco_obj.activo != banco['activo']:
                banco_obj.nombre = banco['nombre']
                banco_obj.activo = banco['activo']
                banco_obj.save()
                print(f"🔄 Actualizado: {banco['nombre']} ({banco['codigo']})")
    
    print(f"\n✅ Total de bancos en la base de datos: {Banco.objects.count()}")

def eliminar_bancos(apps, schema_editor):
    Banco = apps.get_model('myapp', 'Banco')
    Banco.objects.all().delete()
    print("✅ Todos los bancos fueron eliminados")

class Migration(migrations.Migration):
    dependencies = [
        ('myapp', '0040_banco_clienteexterno_detallepagomovil_and_more'),  # Cambia por tu última migración
    ]

    operations = [
        migrations.RunPython(crear_bancos_venezuela, eliminar_bancos),
    ]