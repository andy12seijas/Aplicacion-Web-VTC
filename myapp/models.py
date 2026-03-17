from datetime import timezone
import datetime
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
class PerfilUsuario(models.Model):
    """Modelo para extender la información del usuario"""
    
    usuario = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='perfil',
        verbose_name="Usuario"
    )
    cedula = models.PositiveIntegerField(
        verbose_name="Cédula de Identidad",
        unique=True,
        null=True,
        blank=True
    )
    telefono = models.CharField(
        max_length=20,
        verbose_name="Teléfono",
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"
    
    def __str__(self):
        return f"Perfil de {self.usuario.username}"

class ClientePotencial(models.Model):
    class InteresadoChoices(models.TextChoices):
        SI = 'SI', 'Sí'
        TAL_VEZ = 'TAL_VEZ', 'Tal vez'
        NO = 'NO', 'No'
    
    cedula = models.CharField(max_length=15,verbose_name="Cédula de Identidad",unique=True,  help_text="Ej: V-12345678, E-87654321",db_index=True)
    nombre = models.CharField(max_length=100,verbose_name="Nombre")
    apellido = models.CharField(max_length=100,verbose_name="Apellido")
    direccion = models.TextField(max_length=255,verbose_name="Dirección",blank=True,null=True)
    telefono = models.CharField(max_length=20, verbose_name="Teléfono",help_text="Ej: +58 412-1234567")
    posee_internet = models.BooleanField(default=False,verbose_name="¿Posee internet?", help_text="Marcar si ya tiene servicio de internet")
    interesado = models.CharField(max_length=10,choices=InteresadoChoices.choices,default=InteresadoChoices.TAL_VEZ,verbose_name="Nivel de interés")
    observacion = models.TextField(max_length=500,verbose_name="Observaciones",blank=True,null=True,help_text="Notas adicionales sobre el cliente")
    fecha_registro = models.DateField( default=datetime.date.today, verbose_name="Fecha de registro",help_text="Fecha en que se registró el cliente")
    creado_por = models.ForeignKey(User,on_delete=models.SET_NULL,  null=True,blank=True,related_name='clientes_potenciales_creados', verbose_name="Creado por",help_text="Usuario que registró este cliente")
    fecha_creacion = models.DateTimeField(auto_now_add=True,verbose_name="Fecha de creación en sistema")
    fecha_actualizacion = models.DateTimeField(auto_now=True,verbose_name="Última actualización")
    
    class Meta:
        verbose_name = "Cliente Potencial"
        verbose_name_plural = "Clientes Potenciales"
        ordering = ['-fecha_creacion']  # Ordenar por más recientes primero
        
    def __str__(self):
        return f"{self.nombre} {self.apellido} - {self.get_interesado_display()}"
    
    @property
    def nombre_completo(self):
        """Retorna el nombre completo del cliente"""
        return f"{self.nombre} {self.apellido}".strip()
    
    
class UbicacionUsuario(models.Model):
    """Modelo para almacenar la ubicación ACTUAL de cualquier usuario (vendedor, instalador, etc)"""
    
    usuario = models.OneToOneField(
        User,on_delete=models.CASCADE,related_name='ubicacion',verbose_name="Usuario")
    latitud = models.FloatField(verbose_name="Latitud")
    longitud = models.FloatField(verbose_name="Longitud")
    ultima_actualizacion = models.DateTimeField(auto_now=True,verbose_name="Última actualización")
    class Meta:
        verbose_name = "Ubicación de Usuario"
        verbose_name_plural = "Ubicaciones de Usuarios"
        indexes = [
            models.Index(fields=['ultima_actualizacion']),
        ]
    
    def __str__(self):
        return f"{self.usuario.username} - {self.latitud}, {self.longitud}"
    
    @property
    def esta_activo(self):
        hace_una_hora = timezone.now() - timedelta(hours=1)
        return self.ultima_actualizacion > hace_una_hora
    
class Plan(models.Model):
    """Modelo para Planes a Contratar"""
    nombre = models.CharField(max_length=100,unique=True,verbose_name="Nombre del Plan")
    activo = models.BooleanField(default=True,verbose_name="Activo")
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    
    class Meta:
        verbose_name = "Plan"
        verbose_name_plural = "Planes"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class ModalidadEquipo(models.Model):
    """Modelo para Modalidad del Equipo"""
    nombre = models.CharField(max_length=100,unique=True,verbose_name="Modalidad")
    activo = models.BooleanField(default=True,verbose_name="Activo")
    
    class Meta:
        verbose_name = "Modalidad de Equipo"
        verbose_name_plural = "Modalidades de Equipo"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class TipoVivienda(models.Model):
    """Modelo para Tipo de Vivienda"""
    nombre = models.CharField(max_length=100,unique=True,verbose_name="Tipo de Vivienda")
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    class Meta:
        verbose_name = "Tipo de Vivienda"
        verbose_name_plural = "Tipos de Vivienda"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Red(models.Model):
    """Modelo para Tipo de Red"""
    nombre = models.CharField(max_length=100,unique=True,verbose_name="Red")
    activo = models.BooleanField(default=True,verbose_name="Activo")
    
    class Meta:
        verbose_name = "Red"
        verbose_name_plural = "Redes"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre
    
    
class ContratoCliente(models.Model):
    """Modelo principal para Contratos de Clientes"""
    class SimplePlusChoices(models.TextChoices):
        SI = 'SI', 'Sí'
        NO = 'NO', 'No'
    # Estados del contrato
    class EstadoContrato(models.TextChoices):
        EN_PROCESO = 'EN_PROCESO', 'En Proceso'
        COMPLETADO = 'COMPLETADO', 'Completado'
        NO_COMPLETADO = 'NO_COMPLETADO', 'No Completado'
    
    # Relación con Cliente Potencial
    cliente_potencial = models.ForeignKey('ClientePotencial',on_delete=models.CASCADE,related_name='contratos',verbose_name="Cliente Potencial")
    # ===== NUEVOS CAMPOS =====
    otro_telefono = models.CharField(max_length=20,verbose_name="Otro Teléfono",blank=True,null=True,help_text="Teléfono adicional de contacto")
    correo_electronico = models.EmailField(verbose_name="Correo Electrónico",max_length=254,unique=True)
    direccion_detallada = models.TextField(max_length=500,verbose_name="Dirección Detallada",help_text="Calle, avenida, urbanización, casa/edificio, piso, apartamento")
    fecha_nacimiento = models.DateField(verbose_name="Fecha de Nacimiento")
    # Plan a contratar (relación con tabla Plan)
    plan_contratado = models.ForeignKey(Plan,on_delete=models.PROTECT,related_name='contratos',verbose_name="Plan a Contratar")
    # Simple Plus (campo booleano)
    simple_plus = models.CharField(max_length=2,choices=SimplePlusChoices.choices,default=SimplePlusChoices.NO,verbose_name="Simple Plus",help_text="¿El cliente tiene Simple Plus?")
    # Modalidad del equipo (relación con tabla ModalidadEquipo)
    modalidad_equipo = models.ForeignKey(ModalidadEquipo,on_delete=models.PROTECT,related_name='contratos',verbose_name="Modalidad del Equipo")
    punto_referencia = models.CharField(max_length=255,verbose_name="Punto de Referencia",help_text="Referencia para encontrar la ubicación")
    # Tipo de vivienda (relación con tabla TipoVivienda)
    tipo_vivienda = models.ForeignKey(TipoVivienda,on_delete=models.PROTECT,related_name='contratos',verbose_name="Tipo de Vivienda")
    numero_casa = models.CharField(max_length=50,verbose_name="Número de Casa/Edificio",help_text="Número de la casa, edificio, apartamento")
    # Datos de pago
    numero_pago_movil = models.CharField(max_length=20,verbose_name="Número de Pago Móvil",help_text="Número de teléfono donde se realizó el pago")
    # Subir foto del pago
    foto_pago = models.ImageField(upload_to='pagos/',verbose_name="Foto del Pago",help_text="Captura de pantalla o foto del comprobante de pago")
    # Red (relación con tabla Red)
    red = models.ForeignKey(Red,on_delete=models.PROTECT,related_name='contratos',verbose_name="Red")
    # Campos adicionales (SOLO ADMIN, vendedor no los llena)
    ods = models.CharField(max_length=50,verbose_name="ODS",blank=True,null=True,help_text="Orden de Servicio (solo administrador)")
    customer_id = models.CharField(max_length=50,verbose_name="Customer ID",blank=True,null=True,help_text="ID del cliente en el sistema (solo administrador)")
    atr = models.CharField(default="*VTC Conexiones",max_length=50,verbose_name="ATR",blank=True,null=True,help_text="ATR")
    # Estado del contrato (por defecto EN_PROCESO)
    estado = models.CharField(max_length=15,choices=EstadoContrato.choices,default=EstadoContrato.EN_PROCESO,verbose_name="Estado del Contrato")
    # Campos de control
    creado_por = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='contratos_creados',verbose_name="Creado por")
    fecha_creacion = models.DateTimeField(auto_now_add=True,verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True,verbose_name="Última actualización")
    
    class Meta:
        verbose_name = "Contrato de Cliente"
        verbose_name_plural = "Contratos de Clientes"
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['estado']),
            models.Index(fields=['fecha_creacion']),
            models.Index(fields=['correo_electronico']),
        ]
    
    def __str__(self):
        estado_display = self.get_estado_display()
        return f"Contrato {self.id} - {self.nombre} {self.apellido} [{estado_display}]"
    
    @property
    def cedula(self):
        return self.cliente_potencial.cedula
    
    @property
    def nombre(self):
        return self.cliente_potencial.nombre
    
    @property
    def apellido(self):
        return self.cliente_potencial.apellido
    
    @property
    def telefono_principal(self):
        return self.cliente_potencial.telefono
    
    @property
    def nombre_completo(self):
        return self.cliente_potencial.nombre_completo           