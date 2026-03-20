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
    activo = models.BooleanField(  # Campo nuevo
        default=True,
        verbose_name="Activo"
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
    numero_pago_movil = models.CharField(blank=True, null=True,max_length=20,verbose_name="Número de Pago Móvil",help_text="Número de teléfono donde se realizó el pago")
    # Subir foto del pago
    foto_pago = models.ImageField(blank=True, null=True,upload_to='pagos/',verbose_name="Foto del Pago",help_text="Captura de pantalla o foto del comprobante de pago")
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
    
    
    
class Cuadrilla(models.Model):
    """Modelo para representar una cuadrilla de instaladores"""
    
    class EstadoCuadrilla(models.TextChoices):
        DISPONIBLE = 'DISPONIBLE', 'Disponible'
        OCUPADO = 'OCUPADO', 'Ocupado'
        EN_DESCANSO = 'DESCANSO', 'En Descanso'
        INACTIVO = 'INACTIVO', 'Inactivo'
    
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre de la Cuadrilla"
    )
    codigo = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Código de Cuadrilla",
        help_text="Ej: C001, INST-001"
    )
    # Múltiples instaladores (relación muchos a muchos)
    instaladores = models.ManyToManyField(
        'PerfilUsuario',
        related_name='cuadrillas',
        verbose_name="Instaladores",
        blank=True
    )
    
    estado = models.CharField(
        max_length=20,
        choices=EstadoCuadrilla.choices,
        default=EstadoCuadrilla.DISPONIBLE,
        verbose_name="Estado de la Cuadrilla",
        db_index=True
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cuadrillas_creadas',
        verbose_name="Creado por"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    class Meta:
        verbose_name = "Cuadrilla"
        verbose_name_plural = "Cuadrillas"
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['estado']),
            models.Index(fields=['activo']),
            models.Index(fields=['codigo']),
        ]
    
    def __str__(self):
        instaladores_count = self.instaladores.count()
        return f"{self.codigo} - {self.nombre} ({instaladores_count} instaladores) [{self.get_estado_display()}]"
    
    
class AsignacionContrato(models.Model):
    """Modelo para asignar contratos a cuadrillas"""
    
    contrato = models.ForeignKey(
        'ContratoCliente',
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name="Contrato"
    )
    cuadrilla = models.ForeignKey(
        'Cuadrilla',
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name="Cuadrilla"
    )
    fecha_asignacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de asignación"
    )
    asignado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asignaciones_realizadas',
        verbose_name="Asignado por"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    observaciones = models.TextField(
        max_length=500,
        verbose_name="Observaciones",
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = "Asignación de Contrato"
        verbose_name_plural = "Asignaciones de Contratos"
        ordering = ['-fecha_asignacion']
        indexes = [
            models.Index(fields=['activo']),
            models.Index(fields=['fecha_asignacion']),
        ]
    
    def __str__(self):
        return f"{self.contrato.nombre_completo} → {self.cuadrilla.nombre}"
    
    
    
class ModeloModem(models.Model):
    """Modelo para almacenar los modelos de modem disponibles"""
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Modelo del Modem")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    
    class Meta:
        verbose_name = "Modelo de Módem"
        verbose_name_plural = "Modelos de Módem"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Instalacion(models.Model):
    """Modelo para registrar las instalaciones realizadas por los instaladores"""
    
    # Relación con la asignación
    asignacion = models.OneToOneField(
        'AsignacionContrato',
        on_delete=models.CASCADE,
        related_name='instalacion',
        verbose_name="Asignación"
    )
    
    # Número de orden de servicio autoincremental
    orden_servicio = models.CharField(
        max_length=10,
        
        editable=False,
        verbose_name="Orden de Servicio"
    )
    
    # Datos de ubicación (nuevos)
    feeder = models.CharField(max_length=50, verbose_name="FEEDER", blank=True, null=True)
    caja = models.CharField(max_length=50, verbose_name="CAJA", blank=True, null=True)
    puerto_utilizado = models.CharField(max_length=10, verbose_name="PUERTO UTILIZADO", blank=True, null=True)
    ubicacion_lat = models.FloatField(verbose_name="Latitud", blank=True, null=True)
    ubicacion_lng = models.FloatField(verbose_name="Longitud", blank=True, null=True)
    
    # Datos del equipo
    modelo_modem = models.ForeignKey(
        ModeloModem,
        on_delete=models.PROTECT,
        related_name='instalaciones',
        verbose_name="Modelo del Módem",
        null=True,  blank=True,
    )
    sn_modem = models.CharField(null=True,  blank=True,max_length=50, verbose_name="Serial del Módem")
    mac_modem = models.CharField(null=True,  blank=True,max_length=50, verbose_name="MAC del Módem")
    
    # Materiales utilizados
    inicio_fibra = models.PositiveIntegerField(null=True,blank=True,verbose_name="INICIO", help_text="Medición inicial de fibra")
    final_fibra = models.PositiveIntegerField(null=True, blank=True,verbose_name="FINAL", help_text="Medición final de fibra")
    
    @property
    def metros_utilizados(self):
        """Calcula los metros utilizados"""
        return self.final_fibra - self.inicio_fibra if self.final_fibra and self.inicio_fibra else 0
    
    conectores = models.PositiveIntegerField(null=True,blank=True,verbose_name="CONECTORES", default=0)
    rosetas = models.PositiveIntegerField(null=True,blank=True,verbose_name="ROSETAS", default=0)
    patch_cord = models.PositiveIntegerField(verbose_name="PACH CORD", default=0)
    tensores = models.PositiveIntegerField(null=True,  blank=True,verbose_name="TENSORES", default=0)
    conectores_malos = models.PositiveIntegerField(null=True,blank=True,verbose_name="CONECTORES MALOS", default=0)
    
    # Observaciones
    observacion = models.TextField(max_length=500, verbose_name="OBSERVACIÓN", blank=True, null=True)
    
    # Estado de la instalación
    completada = models.BooleanField(default=False, verbose_name="Completada")
    fecha_instalacion = models.DateTimeField(verbose_name="Fecha de instalación", null=True, blank=True)
    
    # Campos de control
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instalaciones_realizadas',
        verbose_name="Realizada por"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    
    class Meta:
        verbose_name = "Instalación"
        verbose_name_plural = "Instalaciones"
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['orden_servicio']),
            models.Index(fields=['completada']),
            models.Index(fields=['fecha_instalacion']),
        ]
    
    def __str__(self):
        return f"Instalación {self.orden_servicio} - {self.asignacion.contrato.cliente_potencial.nombre_completo}"
    
    @property
    def nombre_cliente(self):
        """Obtener nombre completo del cliente desde el contrato"""
        if hasattr(self, 'asignacion') and self.asignacion:
            return self.asignacion.contrato.cliente_potencial.nombre_completo
        return "Cliente no disponible"
    
    @property
    def cedula_cliente(self):
        """Obtener cédula del cliente desde el contrato"""
        if hasattr(self, 'asignacion') and self.asignacion:
            return self.asignacion.contrato.cliente_potencial.cedula
        return "Cédula no disponible"
    
    @property
    def customer_id(self):
        """Obtener customer ID desde el contrato"""
        if hasattr(self, 'asignacion') and self.asignacion:
            return self.asignacion.contrato.customer_id
        return "Customer ID no disponible"
    
    @property
    def plan(self):
        """Obtener plan desde el contrato"""
        if hasattr(self, 'asignacion') and self.asignacion:
            return self.asignacion.contrato.plan_contratado.nombre
        return "Plan no disponible"
    
    @property
    def atr(self):
        """Obtener ATR desde el contrato"""
        if hasattr(self, 'asignacion') and self.asignacion:
            return self.asignacion.contrato.atr
        return "ATR no disponible"        