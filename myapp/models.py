from datetime import timezone
import datetime
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User

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
        RENUNCIADO = 'RENUNCIADO', 'Renunciado'
    
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
    latitud = models.FloatField(verbose_name="Latitud",blank=True, null=True,help_text="Coordenada de la ubicación del cliente")
    longitud = models.FloatField(verbose_name="Longitud",blank=True, null=True, help_text="Coordenada de la ubicación del cliente")
    cashea = models.BooleanField(
        default=False,
        verbose_name="Cashea"
    )
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
    
    # ========== CAMBIO IMPORTANTE: ya NO usa auto_now_add ==========
    fecha_creacion = models.DateTimeField(verbose_name="Fecha de creación")  # ← CAMBIADO
    
    fecha_actualizacion = models.DateTimeField(auto_now=True,verbose_name="Última actualización")  # ← Este sigue igual
    fecha_completado = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="Fecha de completado",
        help_text="Fecha y hora en que el contrato cambió a COMPLETADO por primera vez"
    )
    
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
    
    # ========== MÉTODO SAVE CORREGIDO ==========
    def save(self, *args, **kwargs):
        import pytz
        from django.utils import timezone
        
        VE_TZ = pytz.timezone('America/Caracas')
        
        # Solo para CONTRATOS NUEVOS (sin ID todavía)
        if not self.pk:
            # Asignar la hora actual de Venezuela
            ahora_ve = timezone.now().astimezone(VE_TZ)
            self.fecha_creacion = ahora_ve
            
            # Si el contrato se crea ya como COMPLETADO
            if self.estado == 'COMPLETADO' and not self.fecha_completado:
                self.fecha_completado = ahora_ve
        
        # Para ACTUALIZACIONES (cuando cambia estado a COMPLETADO)
        if self.pk:
            try:
                old_instance = ContratoCliente.objects.get(pk=self.pk)
                if old_instance.estado != 'COMPLETADO' and self.estado == 'COMPLETADO':
                    if not self.fecha_completado:
                        ahora_ve = timezone.now().astimezone(VE_TZ)
                        self.fecha_completado = ahora_ve
            except ContratoCliente.DoesNotExist:
                pass
        
        # Llamar al save original
        super().save(*args, **kwargs)
    
    
    
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
    @property
    def cantidad_instaladores(self):
        """Retorna la cantidad de instaladores en la cuadrilla"""
        return self.instaladores.count()
    
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
    
    # Relación con ContratoCliente (opcional)
    contrato = models.ForeignKey(
        'ContratoCliente',
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name="Contrato de Vendedor",
        null=True,
        blank=True,
        help_text="Contrato generado por vendedor"
    )
    
    # Relación con VentaDirecta (opcional)
    venta_directa = models.ForeignKey(
        'VentaDirecta',
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name="Venta Directa",
        null=True,
        blank=True,
        help_text="Venta directa de la torre de control"
    )
    
    # Relación con Cuadrilla
    cuadrilla = models.ForeignKey(
        'Cuadrilla',
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name="Cuadrilla"
    )
    trabajo_interno = models.BooleanField(
        default=False,
        verbose_name="Sc",
        null=True,
        blank=True,
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
            models.Index(fields=['contrato']),
            models.Index(fields=['venta_directa']),
        ]
        # Validación: al menos uno de los dos debe estar presente
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(contrato__isnull=False) | 
                    models.Q(venta_directa__isnull=False)
                ),
                name="asignacion_tiene_origen"
            )
        ]
    
    def save(self, *args, **kwargs):
        """Validar que tenga al menos un origen antes de guardar"""
        if not self.contrato and not self.venta_directa:
            raise ValueError("La asignación debe tener un contrato o una venta directa")
        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.contrato:
            return f"{self.contrato.nombre_completo} → {self.cuadrilla.nombre}"
        elif self.venta_directa:
            return f"{self.venta_directa.nombre_completo} → {self.cuadrilla.nombre}"
        return f"Asignación #{self.id} → {self.cuadrilla.nombre}"
    
    @property
    def tipo_asignacion(self):
        """Retorna el tipo de asignación"""
        if self.contrato:
            return "vendedor"
        elif self.venta_directa:
            return "torre_control"
        return "desconocido"
    
    @property
    def cliente_nombre(self):
        """Obtiene el nombre del cliente según el origen"""
        if self.contrato:
            return self.contrato.nombre_completo
        elif self.venta_directa:
            return self.venta_directa.nombre_completo
        return "Cliente no disponible"
    
    @property
    def cedula_cliente(self):
        """Obtiene la cédula del cliente según el origen"""
        if self.contrato:
            return self.contrato.cedula
        elif self.venta_directa:
            return self.venta_directa.cedula
        return "N/A"
    
    @property
    def telefono_cliente(self):
        """Obtiene el teléfono del cliente según el origen"""
        if self.contrato:
            return self.contrato.telefono_principal
        elif self.venta_directa:
            return self.venta_directa.telefono
        return "N/A"
    
    @property
    def plan(self):
        """Obtiene el plan según el origen"""
        if self.contrato:
            return self.contrato.plan_contratado.nombre
        elif self.venta_directa:
            return self.venta_directa.plan.nombre
        return "N/A"
    
    @property
    def direccion(self):
        """Obtiene la dirección según el origen"""
        if self.contrato:
            return self.contrato.direccion_detallada
        elif self.venta_directa:
            return self.venta_directa.direccion if hasattr(self.venta_directa, 'direccion') else "N/A"
        return "N/A"
    
    @property
    def referencia_externa(self):
        """Obtiene referencia externa (número de orden de torre o customer ID)"""
        if self.contrato:
            return self.contrato.customer_id or "N/A"
        elif self.venta_directa:
            return self.venta_directa.nro_orden
        return "N/A"
    
    @property
    def ods(self):
        """Obtiene ODS según el origen"""
        if self.contrato:
            return self.contrato.ods or "N/A"
        elif self.venta_directa:
            return self.venta_directa.ods if hasattr(self.venta_directa, 'ods') else "N/A"
        return "N/A"
    
    
    
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
    instaladores = models.ManyToManyField(
        User,
        related_name='instalaciones',
        verbose_name="Instaladores que realizaron la instalación",
        blank=True
    )
    # Ubicación de la instalación (coordenadas del cliente)
    latitud = models.FloatField(
        verbose_name="Latitud",
        blank=True, null=True,
        help_text="Coordenada de la ubicación del cliente"
    )
    longitud = models.FloatField(
        verbose_name="Longitud",
        blank=True, null=True,
        help_text="Coordenada de la ubicación del cliente"
    )
    
    # Datos técnicos de la instalación
    feeder = models.CharField(
        max_length=50,
        verbose_name="FEEDER",
        blank=True, null=True
    )
    caja = models.CharField(
        max_length=50,
        verbose_name="CAJA",
        blank=True, null=True
    )
    puerto_utilizado = models.CharField(
        max_length=10,
        verbose_name="PUERTO UTILIZADO",
        blank=True, null=True
    )
    
    # Datos del equipo instalado
    modelo_modem = models.ForeignKey(
        'ModeloModem',
        on_delete=models.PROTECT,
        related_name='instalaciones',
        verbose_name="Modelo del Módem",
        null=True, blank=True
    )
    sn_modem = models.CharField(
        max_length=50,
        verbose_name="Serial del Módem",
        blank=True, null=True
    )
    mac_modem = models.CharField(
        max_length=50,
        verbose_name="MAC del Módem",
        blank=True, null=True
    )
    
    # Materiales utilizados
    inicio_fibra = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="INICIO",
        help_text="Medición inicial de fibra"
    )
    final_fibra = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="FINAL",
        help_text="Medición final de fibra"
    )
    
    @property
    def metros_utilizados(self):
        """Calcula los metros utilizados (valor absoluto de la diferencia)"""
        if self.inicio_fibra is not None and self.final_fibra is not None:
            return abs(self.inicio_fibra - self.final_fibra)  # ← Usar abs() para valor absoluto
        return 0
    
    conectores = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="CONECTORES",
        default=0
    )
    rosetas = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="ROSETAS",
        default=0
    )
    patch_cord = models.PositiveIntegerField(
        verbose_name="PACH CORD",
        default=0
    )
    tensores = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="TENSORES",
        default=0
    )
    conectores_malos = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="CONECTORES MALOS",
        default=0
    )
    tirros = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="TIRROS",
        default=0,
        help_text="Cantidad de tirros utilizados en la instalación"
    )
    
    # Fotos de la instalación (múltiples imágenes)
    fotos = models.JSONField(
        default=list,
        verbose_name="Fotos de la instalación",
        help_text="Lista de URLs de las fotos subidas"
    )
    
    # Observaciones
    observacion = models.TextField(
        max_length=500,
        verbose_name="OBSERVACIÓN",
        blank=True, null=True
    )
    
    # Estado de la instalación
    completada = models.BooleanField(
        default=False,
        verbose_name="Completada"
    )
    fecha_instalacion = models.DateTimeField(
        verbose_name="Fecha de instalación",
        null=True, blank=True
    )
    
    # Campos de control
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='instalaciones_realizadas',
        verbose_name="Realizada por"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    
    class Meta:
        verbose_name = "Instalación"
        verbose_name_plural = "Instalaciones"
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['completada']),
            models.Index(fields=['fecha_instalacion']),
        ]
    
    def __str__(self):
        try:
            if self.asignacion.contrato:
                nombre = self.asignacion.contrato.cliente_potencial.nombre_completo
            elif self.asignacion.venta_directa:
                nombre = self.asignacion.venta_directa.nombre_completo
            else:
                nombre = "Cliente no disponible"
            return f"Instalación - {nombre}"
        except:
            return f"Instalación #{self.id}"
    
    @property
    def orden_servicio(self):
        """Obtener ODS desde el contrato o número de orden desde venta directa"""
        if self.asignacion.contrato:
            return self.asignacion.contrato.ods
        elif self.asignacion.venta_directa:
            return self.asignacion.venta_directa.nro_orden
        return "N/A"
    
    @property
    def nombre_cliente(self):
        """Obtener nombre completo del cliente según el origen"""
        if self.asignacion.contrato:
            return self.asignacion.contrato.cliente_potencial.nombre_completo
        elif self.asignacion.venta_directa:
            return self.asignacion.venta_directa.nombre_completo
        return "Cliente no disponible"
    
    @property
    def cedula_cliente(self):
        """Obtener cédula del cliente según el origen"""
        if self.asignacion.contrato:
            return self.asignacion.contrato.cliente_potencial.cedula
        elif self.asignacion.venta_directa:
            return self.asignacion.venta_directa.cedula
        return "N/A"
    
    @property
    def customer_id(self):
        """Obtener customer ID según el origen"""
        if self.asignacion.contrato:
            return self.asignacion.contrato.customer_id or "N/A"
        elif self.asignacion.venta_directa:
            return self.asignacion.venta_directa.customer_id or "N/A"
        return "N/A"
    
    @property
    def plan(self):
        """Obtener plan según el origen"""
        if self.asignacion.contrato:
            return self.asignacion.contrato.plan_contratado.nombre
        elif self.asignacion.venta_directa:
            return self.asignacion.venta_directa.plan.nombre
        return "N/A"
    
    @property
    def atr(self):
        """Obtener ATR desde el contrato o venta directa"""
        if self.asignacion.contrato:
            return self.asignacion.contrato.atr
        elif self.asignacion.venta_directa:
            return "*VTC Conexiones"  # Valor por defecto para ventas directas
        return "N/A"
    
    @property
    def creado_por_nombre(self):
        """Obtener nombre del creador según el origen"""
        if self.asignacion.contrato:
            creador = self.asignacion.contrato.creado_por
            return creador.get_full_name() or creador.username if creador else "Sistema"
        elif self.asignacion.venta_directa:
            creador = self.asignacion.venta_directa.creado_por
            return creador.get_full_name() or creador.username if creador else "Sistema"
        return "Sistema"
    
    @property
    def es_venta_directa(self):
        """Indica si la instalación es de una venta directa"""
        return self.asignacion.venta_directa is not None
    
    @property
    def nro_orden(self):
        """Obtener número de orden de venta directa (si aplica)"""
        if self.asignacion.venta_directa:
            return self.asignacion.venta_directa.nro_orden
        return None
        
        
class VentaDirecta(models.Model):
    """Modelo para ventas directas"""
    
    # Estados de la venta
    class EstadoVenta(models.TextChoices):
        EN_PROCESO = 'EN_PROCESO', 'En Proceso'
        COMPLETADO = 'COMPLETADO', 'Completado'
        NO_COMPLETADO = 'NO_COMPLETADO', 'No Completado'
    
    nro_orden = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Número de Orden",
        help_text="Número único de orden de venta"
    )
    cedula = models.CharField(
        max_length=15,
        verbose_name="Cédula",
        help_text="Cédula del cliente"
    )
    customer_id = models.CharField(
        max_length=50,
        verbose_name="Customer ID",
        blank=True,
        null=True,
        help_text="ID del cliente en el sistema"
    )
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre"
    )
    apellido = models.CharField(
        max_length=100,
        verbose_name="Apellido"
    )
    telefono = models.CharField(
        max_length=20,
        verbose_name="Teléfono",
        help_text="Teléfono de contacto"
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='ventas_directas',
        verbose_name="Plan"
    )
    fecha = models.DateField(
        auto_now_add=True,
        verbose_name="Fecha de venta"
    )
    estado = models.CharField(
        max_length=15,
        choices=EstadoVenta.choices,
        default=EstadoVenta.EN_PROCESO,
        verbose_name="Estado de la Venta"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación en sistema"
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
        related_name='ventas_directas_creadas',
        verbose_name="Creado por"
    )
    observacion = models.TextField(
        max_length=500,
        verbose_name="Observaciones",
        blank=True,
        null=True,
        help_text="Notas adicionales sobre la venta"
    )
    
    class Meta:
        verbose_name = "Venta Directa"
        verbose_name_plural = "Ventas Directas"
        ordering = ['-fecha', '-fecha_creacion']
        indexes = [
            models.Index(fields=['nro_orden']),
            models.Index(fields=['cedula']),
            models.Index(fields=['fecha']),
            models.Index(fields=['estado']),
        ]
    
    def __str__(self):
        return f"{self.nro_orden} - {self.nombre} {self.apellido} - {self.plan.nombre} [{self.get_estado_display()}]"
    
    @property
    def nombre_completo(self):
        """Retorna el nombre completo"""
        return f"{self.nombre} {self.apellido}".strip()
    
    
        
        
        
        
# ==================== NÓMINA DE VENDEDORES ====================

class TasaCambio(models.Model):
    """Modelo para almacenar la tasa de cambio USD/BS"""
    
    tasa = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Tasa de Cambio (USD a Bs)"
    )
    fecha = models.DateField(
        default=datetime.date.today,
        verbose_name="Fecha de vigencia"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    class Meta:
        verbose_name = "Tasa de Cambio"
        verbose_name_plural = "Tasas de Cambio"
        ordering = ['-fecha']
    
    def __str__(self):
        return f"1 USD = {self.tasa} Bs ({self.fecha})"
    
    def save(self, *args, **kwargs):
        if self.activo:
            TasaCambio.objects.filter(activo=True).update(activo=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_tasa_activa(cls):
        """Obtiene la tasa de cambio activa actual"""
        tasa_obj = cls.objects.filter(activo=True).first()
        if tasa_obj:
            return tasa_obj.tasa
        ultima_tasa = cls.objects.order_by('-fecha').first()
        return ultima_tasa.tasa if ultima_tasa else 0


class NominaVendedor(models.Model):
    """Modelo para la nómina de vendedores"""
    
    class RangoContratos(models.TextChoices):
        RANGO_1_5 = '1-5', '1 a 5 contratos'
        RANGO_6_10 = '6-10', '6 a 10 contratos'
        RANGO_11_MAS = '11+', '11 o más contratos'
    
    vendedor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='nominas',
        verbose_name="Vendedor"
    )
    semana_inicio = models.DateField(
        verbose_name="Inicio de semana (viernes)"
    )
    semana_fin = models.DateField(
        verbose_name="Fin de semana (viernes siguiente)"
    )
    total_contratos = models.PositiveIntegerField(
        default=0,
        verbose_name="Total contratos completados en la semana"
    )
    rango = models.CharField(
        max_length=10,
        choices=RangoContratos.choices,
        blank=True,
        null=True,
        verbose_name="Rango alcanzado"
    )
    comision_por_contrato = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Comisión por contrato (USD)"
    )
    comision_total_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Total comisiones (USD)"
    )
    bono_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Bono semanal (USD)"
    )
    total_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Total a pagar (USD)"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Nómina de Vendedor"
        verbose_name_plural = "Nóminas de Vendedores"
        ordering = ['-semana_inicio', 'vendedor__username']
        unique_together = ['vendedor', 'semana_inicio']
    
    def __str__(self):
        return f"{self.vendedor.get_full_name() or self.vendedor.username} - Semana {self.semana_inicio.strftime('%d/%m')} al {self.semana_fin.strftime('%d/%m')}"
    
    def calcular_comision_y_bono(self):
        """Calcula comisión y bono según la cantidad de contratos de la semana"""
        cant = self.total_contratos
        
        if cant >= 1 and cant <= 5:
            self.comision_por_contrato = 8
            self.bono_usd = 20
            self.rango = self.RangoContratos.RANGO_1_5
        elif cant >= 6 and cant <= 10:
            self.comision_por_contrato = 10
            self.bono_usd = 40
            self.rango = self.RangoContratos.RANGO_6_10
        elif cant >= 11:
            self.comision_por_contrato = 10
            self.bono_usd = 60
            self.rango = self.RangoContratos.RANGO_11_MAS
        else:
            self.comision_por_contrato = 0
            self.bono_usd = 0
            self.rango = None
        
        self.comision_total_usd = cant * self.comision_por_contrato
        self.total_usd = self.comision_total_usd + self.bono_usd
    
    @property
    def total_bs(self):
        """Calcula el total en Bolívares usando la tasa de cambio activa"""
        tasa = TasaCambio.get_tasa_activa()
        return self.total_usd * tasa
    
    def save(self, *args, **kwargs):
        self.calcular_comision_y_bono()
        super().save(*args, **kwargs)        
        
class Ticket(models.Model):
    """Modelo para registrar tickets de soporte (fallas, problemas, etc.)"""
    
    class EstadoTicket(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        ASIGNADO = 'ASIGNADO', 'Asignado'
        EN_PROCESO = 'EN_PROCESO', 'En Proceso'
        RESUELTO = 'RESUELTO', 'Resuelto'
        CERRADO = 'CERRADO', 'Cerrado'
        CANCELADO = 'CANCELADO', 'Cancelado'
    
    # Tipos de soporte
    class TipoSoporteTicket(models.TextChoices):
        MUDANZA = 'MUDANZA', 'Mudanza'
        RETIRO = 'RETIRO', 'Retiro'
        RECABLEADO = 'RECABLEADO', 'Recableado'
        SOPORTE = 'SOPORTE', 'Soporte Técnico'
    
    # Información del ticket padre
    ticket_padre = models.CharField(
        max_length=50,
        verbose_name="Ticket Padre",
        help_text="Ej: SIMPLETV-06319623",
        db_index=True
    )
    
    # Tipo de soporte
    tipo_soporte = models.CharField(
        max_length=20,
        choices=TipoSoporteTicket.choices,
        default=TipoSoporteTicket.SOPORTE,
        verbose_name="Tipo de Soporte",
        db_index=True
    )
    
    # Información del cliente
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre"
    )
    apellido = models.CharField(
        max_length=100,
        verbose_name="Apellido"
    )
    cedula = models.CharField(
        max_length=15,
        verbose_name="Cédula",
        db_index=True
    )
    customer_id = models.CharField(
        max_length=50,
        verbose_name="Customer ID",
        blank=True,
        null=True,
        db_index=True
    )
    telefono = models.CharField(
        max_length=20,
        verbose_name="Teléfono"
    )

    
    # Dirección completa (un solo campo)
    direccion = models.TextField(
        max_length=500,
        verbose_name="Dirección",
        help_text="Dirección completa del cliente (calle, avenida, urbanización, casa/edificio, referencia)"
    )
    
    # Información del plan (usando la tabla Plan existente)
    plan = models.ForeignKey(
        'Plan',
        on_delete=models.PROTECT,
        related_name='tickets',
        verbose_name="Plan Contratado"
    )
    
    # Detalles de la falla/solicitud
    falla = models.CharField(
        max_length=255,
        verbose_name="Falla o Solicitud",
        help_text="Ej: Sin conexión a internet, Mudanza, Retiro de equipo, etc."
    )
    
    
    # Estado del ticket
    estado = models.CharField(
        max_length=20,
        choices=EstadoTicket.choices,
        default=EstadoTicket.PENDIENTE,
        verbose_name="Estado del Ticket",
        db_index=True
    )
    
    # Fechas importantes
    fecha_reporte = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha y hora del reporte"
    )
    fecha_requerida = models.DateTimeField(
        verbose_name="Fecha y hora requerida para el servicio",
        blank=True,
        null=True
    )
    
    # Campos de control
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets_creados',
        verbose_name="Creado por"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación en sistema"
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    
    # Observaciones generales
    observaciones = models.TextField(
        max_length=500,
        verbose_name="Observaciones",
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = "Ticket de Soporte"
        verbose_name_plural = "Tickets de Soporte"
        ordering = ['-fecha_reporte']
        indexes = [
            models.Index(fields=['ticket_padre']),
            models.Index(fields=['cedula']),
            models.Index(fields=['estado']),
            models.Index(fields=['tipo_soporte']),
            models.Index(fields=['fecha_reporte']),
        ]
    
    def __str__(self):
        return f"{self.ticket_padre} - {self.get_tipo_soporte_display()} - {self.nombre} {self.apellido} [{self.get_estado_display()}]"
    
    @property
    def nombre_completo(self):
        """Retorna el nombre completo del cliente"""
        return f"{self.nombre} {self.apellido}".strip()
    
    @property
    def es_mudanza(self):
        return self.tipo_soporte == self.TipoSoporteTicket.MUDANZA
    
    @property
    def es_retiro(self):
        return self.tipo_soporte == self.TipoSoporteTicket.RETIRO
    
    @property
    def es_recableado(self):
        return self.tipo_soporte == self.TipoSoporteTicket.RECABLEADO
    
    @property
    def es_soporte(self):
        return self.tipo_soporte == self.TipoSoporteTicket.SOPORTE


class AsignacionSoporte(models.Model):
    """Modelo para asignar tickets a cuadrillas"""
    
    # Relación con Ticket
    ticket = models.ForeignKey(
        'Ticket',
        on_delete=models.CASCADE,
        related_name='asignaciones',
        verbose_name="Ticket de Soporte"
    )
    
    # Relación con Cuadrilla
    cuadrilla = models.ForeignKey(
        'Cuadrilla',
        on_delete=models.CASCADE,
        related_name='asignaciones_soporte',
        verbose_name="Cuadrilla asignada"
    )
    
    # Fecha de asignación
    fecha_asignacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de asignación"
    )
    
    # Quién realizó la asignación
    asignado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asignaciones_soporte_realizadas',
        verbose_name="Asignado por"
    )
    
    # Fecha límite para resolver
    
    
    # Estado de la asignación
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    # Observaciones de la asignación
    observaciones = models.TextField(
        max_length=500,
        verbose_name="Observaciones",
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = "Asignación de Soporte"
        verbose_name_plural = "Asignaciones de Soporte"
        ordering = ['-fecha_asignacion']
        indexes = [
            models.Index(fields=['activo']),
            models.Index(fields=['fecha_asignacion']),
            models.Index(fields=['ticket']),
            models.Index(fields=['cuadrilla']),
        ]
    
    def __str__(self):
        return f"{self.ticket.ticket_padre} → {self.cuadrilla.nombre}"
    
    @property
    def cliente_nombre(self):
        """Obtiene el nombre del cliente"""
        return self.ticket.nombre_completo
    
    @property
    def cedula_cliente(self):
        """Obtiene la cédula del cliente"""
        return self.ticket.cedula
    
    @property
    def telefono_cliente(self):
        """Obtiene el teléfono del cliente"""
        return self.ticket.telefono
    
    @property
    def direccion(self):
        """Obtiene la dirección del cliente"""
        return self.ticket.direccion
    
    @property
    def falla(self):
        """Obtiene la falla reportada"""
        return self.ticket.falla
    
    def save(self, *args, **kwargs):
        """Al guardar la asignación, actualiza el estado del ticket a ASIGNADO"""
        super().save(*args, **kwargs)
        # Actualizar estado del ticket
        if self.ticket.estado == 'PENDIENTE':
            self.ticket.estado = 'ASIGNADO'
            self.ticket.save(update_fields=['estado', 'fecha_actualizacion'])


class Soporte(models.Model):
    """Modelo para registrar la ejecución del soporte técnico por parte de los instaladores"""
    
    class EstadoEjecucion(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        EN_PROCESO = 'EN_PROCESO', 'En Proceso'
        COMPLETADO = 'COMPLETADO', 'Completado'
        NO_COMPLETADO = 'NO_COMPLETADO', 'No Completado'
    
    # Relación con la asignación de soporte
    asignacion = models.OneToOneField(
        'AsignacionSoporte',
        on_delete=models.CASCADE,
        related_name='soporte_ejecucion',
        verbose_name="Asignación de Soporte",
        null=True,  # <-- AGREGAR ESTO TEMPORALMENTE
        blank=True
    )
    
    # Instaladores que realizaron el soporte (historial)
    instaladores = models.ManyToManyField(
        User,
        related_name='soportes_tecnicos_realizados',
        verbose_name="Instaladores que realizaron el soporte"
    )
    
    # Cuadrilla que realizó el soporte (para referencia)
    cuadrilla = models.ForeignKey(
        'Cuadrilla',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='soportes_tecnicos',
        verbose_name="Cuadrilla ejecutora"
    )
    
    # Estado de la ejecución
    estado = models.CharField(
        max_length=20,
        choices=EstadoEjecucion.choices,
        default=EstadoEjecucion.PENDIENTE,
        verbose_name="Estado de la ejecución",
        db_index=True
    )
    
    # ===== CAMPOS DEL SERVICIO REALIZADO =====
    fecha_hora_servicio = models.DateTimeField(
        verbose_name="Fecha y hora del servicio realizado",
        null=True,
        blank=True,
        help_text="Fecha y hora en que se realizó el servicio"
    )
    
    falla_encontrada = models.TextField(
        max_length=500,
        verbose_name="Falla encontrada",
        blank=True,
        null=True,
        help_text="Breve descripción de la falla encontrada"
    )
    
    solucion = models.TextField(
        max_length=500,
        verbose_name="Solución aplicada",
        blank=True,
        null=True,
        help_text="Breve descripción de la solución aplicada"
    )
    
    # ===== DATOS TÉCNICOS DEL EQUIPO =====
    modelo_modem = models.ForeignKey(
        'ModeloModem',
        on_delete=models.PROTECT,
        related_name='soportes_tecnicos',
        verbose_name="Modelo del Módem",
        null=True,
        blank=True
    )
    sn_modem = models.CharField(
        max_length=50,
        verbose_name="Serial del Módem",
        blank=True,
        null=True
    )
    mac_modem = models.CharField(
        max_length=50,
        verbose_name="MAC del Módem",
        blank=True,
        null=True
    )
    modem_viejo = models.CharField(
        max_length=50,
        verbose_name="Modelo del Módem viejo",
        blank=True,
        null=True
    )
    sn_modem_viejo = models.CharField(
        max_length=50,
        verbose_name="Serial del Módem Viejo",
        blank=True,
        null=True
    )
    mac_modem_viejo = models.CharField(
        max_length=50,
        verbose_name="MAC del Módem Viejo",
        blank=True,
        null=True
    )
    
    # ===== MEDICIONES DE FIBRA =====
    inicio_fibra = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="INICIO",
        help_text="Medición inicial de fibra"
    )
    final_fibra = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="FINAL",
        help_text="Medición final de fibra"
    )
    
    @property
    def metros_utilizados(self):
        """Calcula los metros utilizados (valor absoluto de la diferencia)"""
        if self.inicio_fibra is not None and self.final_fibra is not None:
            return abs(self.inicio_fibra - self.final_fibra)
        return 0
    
    # ===== MATERIALES UTILIZADOS =====
    conectores = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="CONECTORES",
        default=0
    )
    rosetas = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="ROSETAS",
        default=0
    )
    patch_cord = models.PositiveIntegerField(
        verbose_name="PATCH CORD",
        default=0
    )
    tensores = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="TENSORES",
        default=0
    )
    conectores_malos = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="CONECTORES MALOS",
        default=0
    )
    tirros = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="TIRROS",
        default=0,
        help_text="Cantidad de tirros utilizados"
    )
    
    # ===== DATOS DE LA CAJA NAP =====
    caja_nap_utilizada = models.CharField(
        max_length=100,
        verbose_name="Caja NAP utilizada",
        blank=True, null=True,
        help_text="Nomenclatura de la caja NAP"
    )
    puerto_nap_utilizado = models.CharField(
        max_length=20,
        verbose_name="Puerto en caja NAP utilizado",
        blank=True, null=True
    )
    
    # ===== UBICACIÓN (PIN) =====
    pin_ubicacion_lat = models.FloatField(
        verbose_name="Latitud del pin de ubicación",
        blank=True, null=True,
        help_text="Coordenada de latitud donde se realizó el soporte"
    )
    pin_ubicacion_lng = models.FloatField(
        verbose_name="Longitud del pin de ubicación",
        blank=True, null=True,
        help_text="Coordenada de longitud donde se realizó el soporte"
    )
    
    @property
    def pin_ubicacion(self):
        """Retorna el pin de ubicación como string"""
        if self.pin_ubicacion_lat and self.pin_ubicacion_lng:
            return f"{self.pin_ubicacion_lat}, {self.pin_ubicacion_lng}"
        return ""
    
    # ===== FOTOS =====
    fotos = models.JSONField(
        default=list,
        verbose_name="Soporte fotográfico",
        help_text="Lista de URLs de las fotos (equipos, material, falla, solución, speed test)"
    )
    
    # ===== OBSERVACIONES =====
    observaciones = models.TextField(
        max_length=500,
        verbose_name="Observaciones",
        blank=True, null=True
    )
    
    # ===== FECHAS DE CONTROL =====
    fecha_inicio = models.DateTimeField(
        verbose_name="Fecha de inicio del servicio",
        null=True, blank=True
    )
    fecha_fin = models.DateTimeField(
        verbose_name="Fecha de finalización del servicio",
        null=True, blank=True
    )
    
    # Campos de control
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='soportes_tecnicos_creados',
        verbose_name="Creado por"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    
    class Meta:
        verbose_name = "Soporte Técnico"
        verbose_name_plural = "Soportes Técnicos"
        ordering = ['-fecha_creacion']
        #    models.Index(fields=['estado']),
         #   models.Index(fields=['fecha_hora_servicio']),
         #   models.Index(fields=['asignacion']),
        #]
    
    def __str__(self):
        try:
            ticket = self.asignacion.ticket
            return f"Soporte Técnico - {ticket.ticket_padre} - {ticket.nombre_completo}"
        except:
            return f"Soporte Técnico #{self.id}"
    
    @property
    def esta_completo(self):
        """Verifica si el soporte tiene toda la información requerida"""
        return bool(
            self.fecha_hora_servicio and
            self.falla_encontrada and
            self.solucion and
            self.fotos and
            self.puerto_nap_utilizado and
            self.caja_nap_utilizada and
            self.pin_ubicacion_lat and
            self.pin_ubicacion_lng
        )
    
    @property
    def nombre_cliente(self):
        """Obtiene el nombre del cliente desde el ticket"""
        return self.asignacion.ticket.nombre_completo
    
    @property
    def cedula_cliente(self):
        """Obtiene la cédula del cliente"""
        return self.asignacion.ticket.cedula
    
    @property
    def customer_id(self):
        """Obtiene el customer ID"""
        return self.asignacion.ticket.customer_id
    
    @property
    def direccion(self):
        """Obtiene la dirección del cliente"""
        return self.asignacion.ticket.direccion
    
    @property
    def plan(self):
        """Obtiene el plan contratado"""
        return self.asignacion.ticket.plan.nombre
    
    @property
    def ticket_padre(self):
        """Obtiene el número de ticket padre"""
        return self.asignacion.ticket.ticket_padre
    
    def save(self, *args, **kwargs):
        """Al guardar, actualizar el estado del ticket"""
        super().save(*args, **kwargs)
        
        # Actualizar estado del ticket según el estado de ejecución
        ticket = self.asignacion.ticket
        
        if self.estado == 'COMPLETADO':
            ticket.estado = 'RESUELTO'
        elif self.estado == 'EN_PROCESO':
            ticket.estado = 'EN_PROCESO'
        elif self.estado == 'NO_COMPLETADO':
            ticket.estado = 'PENDIENTE'
        
        ticket.save(update_fields=['estado', 'fecha_actualizacion'])
    
    
# ==================== INVENTARIO SIMPLIFICADO ====================

class Material(models.Model):
    """Materiales disponibles en inventario"""
    
    nombre = models.CharField(max_length=50, unique=True, verbose_name="Nombre del material")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materiales"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class InventarioGlobal(models.Model):
    """Inventario global de materiales (stock general)"""
    
    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        related_name='inventario_global',
        verbose_name="Material"
    )
    cantidad = models.PositiveIntegerField(default=0, verbose_name="Cantidad disponible")
    cantidad_minima = models.PositiveIntegerField(default=5, verbose_name="Cantidad mínima de alerta")
    ultima_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    actualizado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actualizaciones_inventario',
        verbose_name="Actualizado por"
    )
    
    class Meta:
        verbose_name = "Inventario Global"
        verbose_name_plural = "Inventario Global"
        unique_together = ['material']
    
    def __str__(self):
        return f"{self.material.nombre}: {self.cantidad}"
    
    @property
    def esta_bajo_stock(self):
        return self.cantidad <= self.cantidad_minima


class InventarioCuadrilla(models.Model):
    """Inventario asignado a cada cuadrilla"""
    
    cuadrilla = models.ForeignKey(
        Cuadrilla,
        on_delete=models.CASCADE,
        related_name='inventario',
        verbose_name="Cuadrilla"
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='inventario_cuadrillas',
        verbose_name="Material"
    )
    cantidad = models.PositiveIntegerField(default=0, verbose_name="Cantidad en cuadrilla")
    ultima_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Inventario de Cuadrilla"
        verbose_name_plural = "Inventarios de Cuadrillas"
        unique_together = ['cuadrilla', 'material']
    
    def __str__(self):
        return f"{self.cuadrilla.nombre} - {self.material.nombre}: {self.cantidad}"


class MovimientoInventario(models.Model):
    """Registro de todos los movimientos de inventario"""
    
    class TipoMovimiento(models.TextChoices):
        ENTRADA = 'ENTRADA', 'Entrada (Compra/Adición)'
        SALIDA_A_CUADRILLA = 'SALIDA_CUADRILLA', 'Salida a cuadrilla'
        DEVOLUCION_CUADRILLA = 'DEVOLUCION', 'Devolución de cuadrilla'
        GASTO_INSTALACION = 'GASTO_INSTALACION', '🔧 Gasto en instalación'
        GASTO_SOPORTE = 'GASTO_SOPORTE', 'Gasto en soporte'
        AJUSTE = 'AJUSTE', 'Ajuste manual'
    
    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        related_name='movimientos',
        verbose_name="Material"
    )
    tipo = models.CharField(
        max_length=30,
        choices=TipoMovimiento.choices,
        verbose_name="Tipo de movimiento"
    )
    cantidad = models.IntegerField(verbose_name="Cantidad")
    
    # Referencias
    cuadrilla = models.ForeignKey(
        Cuadrilla,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_inventario',
        verbose_name="Cuadrilla relacionada"
    )
    instalacion = models.ForeignKey(
        'Instalacion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_inventario',
        verbose_name="Instalación relacionada"
    )
    soporte = models.ForeignKey(
        'Soporte',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_inventario',
        verbose_name="Soporte relacionado"
    )
    
    observacion = models.TextField(max_length=500, blank=True, null=True)
    fecha_movimiento = models.DateTimeField(auto_now_add=True)
    realizado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_inventario',
        verbose_name="Realizado por"
    )
    
    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ['-fecha_movimiento']
    
    def __str__(self):
        signo = "+" if self.cantidad > 0 else ""
        return f"{signo}{self.cantidad} {self.material.nombre} - {self.fecha_movimiento.strftime('%d/%m/%Y %H:%M')}"    
    
    
# models.py - Agrega este signal al final del archivo

from django.db.models.signals import pre_save
from django.dispatch import receiver

@receiver(pre_save, sender=ContratoCliente)
def actualizar_fecha_completado(sender, instance, **kwargs):
    """Actualiza fecha_completado SOLO la primera vez que cambia a COMPLETADO"""
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            # Si cambiò a COMPLETADO y antes NO estaba completado
            if old_instance.estado != 'COMPLETADO' and instance.estado == 'COMPLETADO':
                # Solo si no tiene fecha_completado (para no sobrescribir)
                if not instance.fecha_completado:
                    instance.fecha_completado = timezone.now()
        except sender.DoesNotExist:
            pass
    else:
        # Contrato nuevo que ya está COMPLETADO desde el inicio
        if instance.estado == 'COMPLETADO' and not instance.fecha_completado:
            instance.fecha_completado = timezone.now()    




#Call center
# 
# 
# 
# 
#             
# ==================== CALL CENTER - REPORTE DE PAGOS ====================

# ==================== CALL CENTER - REPORTE DE PAGOS ====================

class Banco(models.Model):
    """Modelo para almacenar los bancos disponibles"""
    
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre del Banco"
    )
    codigo = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Código del Banco",
        help_text="Ej: 0102, 0134, etc."
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Banco"
        verbose_name_plural = "Bancos"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class ClienteExterno(models.Model):
    """Modelo para clientes que NO están en el sistema principal (ContratoCliente)"""
    
    cedula = models.CharField(
        max_length=15,
        unique=True,
        verbose_name="Cédula",
        db_index=True
    )
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre"
    )
    apellido = models.CharField(
        max_length=100,
        verbose_name="Apellido"
    )
    telefono = models.CharField(
        max_length=20,
        verbose_name="Teléfono"
    )
    correo = models.EmailField(
        verbose_name="Correo electrónico"
    )
    direccion = models.TextField(
        max_length=500,
        verbose_name="Dirección",
        blank=True,
        null=True
    )
    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )
    
    class Meta:
        verbose_name = "Cliente Externo"
        verbose_name_plural = "Clientes Externos"
        ordering = ['-fecha_registro']
    
    def __str__(self):
        return f"{self.nombre} {self.apellido} - {self.cedula}"
    
    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()


class DetallePagoMovil(models.Model):
    """Detalles específicos para pagos realizados por Pago Móvil"""
    
    banco_emisor = models.ForeignKey(
        Banco,
        on_delete=models.PROTECT,
        related_name='pagos_movil_emisor',
        verbose_name="Banco emisor (desde donde pagas)"
    )
    
    numero_telefono = models.CharField(
        max_length=20,
        verbose_name="Número de teléfono",
        help_text="Número desde donde se realizó el Pago Móvil"
    )
   
    
    
    class Meta:
        verbose_name = "Detalle Pago Móvil"
        verbose_name_plural = "Detalles Pago Móvil"
    
    def __str__(self):
        return f"Pago Móvil - {self.banco_emisor} → "


class DetalleTransferencia(models.Model):
    """Detalles específicos para pagos realizados por Transferencia Bancaria"""
    
    banco_origen = models.ForeignKey(
        Banco,
        on_delete=models.PROTECT,
        related_name='transferencias_origen',
        verbose_name="Banco de origen"
    )
    banco_destino = models.ForeignKey(
        Banco,
        on_delete=models.PROTECT,
        related_name='transferencias_destino',
        verbose_name="Banco de destino"
    )
    cedula_titular = models.CharField(
        max_length=15,
        verbose_name="Cédula del titular",
        help_text="Cédula de la persona que realizó la transferencia"
    )
    numero_cuenta_origen = models.CharField(
        max_length=20,
        verbose_name="Número de cuenta origen",
        blank=True,
        null=True
    )
    referencia = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Número de referencia"
    )
    
    class Meta:
        verbose_name = "Detalle Transferencia"
        verbose_name_plural = "Detalles Transferencia"
    
    def __str__(self):
        return f"Transferencia - {self.banco_origen} → {self.banco_destino} - Ref: {self.referencia}"


class ReportePago(models.Model):
    """Modelo principal para reportes de pago"""
    
    class EstadoReporte(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de validación'
        VERIFICADO = 'VERIFICADO', 'Verificado'
        RECHAZADO = 'RECHAZADO', 'Rechazado'
        APLICADO = 'APLICADO', 'Aplicado al contrato'
    
    class MedioPago(models.TextChoices):
        PAGO_MOVIL = 'PAGO_MOVIL', 'Pago Móvil'
        TRANSFERENCIA = 'TRANSFERENCIA', 'Transferencia Bancaria'
    
    # ===== RELACIONES (UNA DE LAS DOS PUEDE ESTAR PRESENTE) =====
    # Cliente interno (ya tiene contrato en tu sistema)
    contrato = models.ForeignKey(
        'ContratoCliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reportes_pago',
        verbose_name="Contrato asociado (cliente interno)"
    )
    
    # Cliente externo (no está en tu sistema)
    cliente_externo = models.ForeignKey(
        ClienteExterno,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reportes_pago',
        verbose_name="Cliente externo (no está en sistema)"
    )
    
    # Flag para saber de dónde viene
    tipo_cliente = models.CharField(
        max_length=10,
        choices=[('INTERNO', 'Cliente interno'), ('EXTERNO', 'Cliente externo')],
        verbose_name="Tipo de cliente"
    )
    
    # ===== INFORMACIÓN DEL PAGO =====
    medio_pago = models.CharField(
        max_length=20,
        choices=MedioPago.choices,
        verbose_name="Medio de pago"
    )
    monto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Monto pagado (Bs)"
    )
    fecha_pago = models.DateField(
        verbose_name="Fecha del pago"
    )
    comprobante = models.ImageField(
        upload_to='comprobantes_pagos/%Y/%m/',
        verbose_name="Comprobante de pago"
    )
    observacion_cliente = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Observaciones del cliente"
    )
    
    # ===== DETALLES ESPECÍFICOS =====
    detalle_pago_movil = models.OneToOneField(
        DetallePagoMovil,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reporte_pago',
        verbose_name="Detalle Pago Móvil"
    )
    detalle_transferencia = models.OneToOneField(
        DetalleTransferencia,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reporte_pago',
        verbose_name="Detalle Transferencia"
    )
    
    # ===== ESTADO Y VALIDACIÓN =====
    estado = models.CharField(
        max_length=20,
        choices=EstadoReporte.choices,
        default=EstadoReporte.PENDIENTE,
        verbose_name="Estado del reporte",
        db_index=True
    )
    rechazo_motivo = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Motivo de rechazo"
    )
    
    # ===== METADATOS =====
    fecha_reporte = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha del reporte"
    )
    fecha_verificacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de verificación"
    )
    verificado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reportes_verificados',
        verbose_name="Verificado por"
    )
    
    # Auditoría
    ip_cliente = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP del cliente"
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name="Navegador/Dispositivo"
    )
    
    class Meta:
        verbose_name = "Reporte de Pago"
        verbose_name_plural = "Reportes de Pagos"
        ordering = ['-fecha_reporte']
        indexes = [
            models.Index(fields=['contrato']),
            models.Index(fields=['cliente_externo']),
            models.Index(fields=['estado']),
            models.Index(fields=['fecha_reporte']),
            models.Index(fields=['medio_pago']),
            models.Index(fields=['tipo_cliente']),
        ]
    
    def __str__(self):
        if self.es_cliente_interno:
            cliente_nombre = self.contrato.nombre_completo
        elif self.es_cliente_externo:
            cliente_nombre = self.cliente_externo.nombre_completo
        else:
            cliente_nombre = "Cliente sin identificar"
        
        return f"Reporte {self.id} - {cliente_nombre} - {self.monto} Bs [{self.get_estado_display()}]"
    
    @property
    def nombre_cliente(self):
        """Obtiene el nombre del cliente desde la relación correspondiente"""
        if self.es_cliente_interno:
            return self.contrato.nombre_completo
        elif self.es_cliente_externo:
            return self.cliente_externo.nombre_completo
        return "N/A"
    
    @property
    def cedula_cliente(self):
        """Obtiene la cédula del cliente desde la relación correspondiente"""
        if self.es_cliente_interno:
            return self.contrato.cedula
        elif self.es_cliente_externo:
            return self.cliente_externo.cedula
        return "N/A"
    
    @property
    def telefono_cliente(self):
        """Obtiene el teléfono del cliente desde la relación correspondiente"""
        if self.es_cliente_interno:
            return self.contrato.telefono_principal
        elif self.es_cliente_externo:
            return self.cliente_externo.telefono
        return "N/A"
    
    @property
    def correo_cliente(self):
        """Obtiene el correo del cliente desde la relación correspondiente"""
        if self.es_cliente_interno:
            return self.contrato.correo_electronico
        elif self.es_cliente_externo:
            return self.cliente_externo.correo
        return "N/A"
    
    @property
    def es_cliente_interno(self):
        return self.tipo_cliente == 'INTERNO' and self.contrato is not None
    
    @property
    def es_cliente_externo(self):
        return self.tipo_cliente == 'EXTERNO' and self.cliente_externo is not None


class RegistroValidacionPago(models.Model):
    """Registro de las validaciones realizadas por call center"""
    
    class AccionValidacion(models.TextChoices):
        VERIFICADO = 'VERIFICADO', '✅ Verificado correcto'
        RECHAZADO = 'RECHAZADO', '❌ Rechazado'
        APLICADO = 'APLICADO', '📄 Aplicado a contrato'
        CREAR_CONTRATO = 'CREAR_CONTRATO', '🆕 Crear contrato (externo → interno)'
        NOTA_INTERNA = 'NOTA_INTERNA', '📝 Nota interna'
    
    reporte = models.ForeignKey(
        ReportePago,
        on_delete=models.CASCADE,
        related_name='validaciones',
        verbose_name="Reporte de pago"
    )
    
    accion = models.CharField(
        max_length=20,
        choices=AccionValidacion.choices,
        verbose_name="Acción"
    )
    
    # Si se crea un contrato para un cliente nuevo, se guarda aquí
    contrato_creado = models.ForeignKey(
        'ContratoCliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validaciones_pago',
        verbose_name="Contrato creado (cliente externo migrado)"
    )
    
    fecha_validacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de validación"
    )
    validado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validaciones_realizadas',
        verbose_name="Validado por"
    )
    nota_interna = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Nota interna"
    )
    
    class Meta:
        verbose_name = "Registro de Validación"
        verbose_name_plural = "Registros de Validaciones"
        ordering = ['-fecha_validacion']
        indexes = [
            models.Index(fields=['reporte']),
            models.Index(fields=['fecha_validacion']),
            models.Index(fields=['accion']),
        ]
    
    def __str__(self):
        return f"{self.get_accion_display()} - {self.reporte} ({self.fecha_validacion.strftime('%d/%m/%Y %H:%M')})"



# ==================== SOPORTE AL CLIENTE (VERSIÓN SIMPLE) ====================

class SoporteCliente(models.Model):
    """Modelo para registrar reclamos y soporte de clientes"""
    
    class EstadoSoporte(models.TextChoices):
        NO_LEIDO = 'NO_LEIDO', 'No leído'
        LEIDO = 'LEIDO', 'Leído'
    
    # Relaciones (una de las dos puede estar presente)
    contrato = models.ForeignKey(
        'ContratoCliente',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='soportes_cliente',
        verbose_name="Contrato del cliente"
    )
    
    cliente_externo = models.ForeignKey(
        'ClienteExterno',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='soportes_cliente',
        verbose_name="Cliente externo"
    )
    
    tipo_cliente = models.CharField(
        max_length=10,
        choices=[('INTERNO', 'Cliente con contrato'), ('EXTERNO', 'Cliente externo')],
        verbose_name="Tipo de cliente"
    )
    
    # Información del soporte
    reclamo = models.TextField(
        max_length=1000,
        verbose_name="Reclamo"
    )
    
    observacion = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Observaciones"
    )
    
    foto = models.ImageField(
        upload_to='soportes_clientes/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="Foto"
    )
    
    # Estado
    estado = models.CharField(
        max_length=20,
        choices=EstadoSoporte.choices,
        default=EstadoSoporte.NO_LEIDO,
        verbose_name="Estado",
        db_index=True
    )
    
    # Fecha en que fue leído por primera vez
    fecha_leido = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de lectura",
        help_text="Fecha y hora en que el soporte fue leído por primera vez por el personal"
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='soportes_cliente_creados',
        verbose_name="Creado por"
    )
    
    class Meta:
        verbose_name = "Soporte a Cliente"
        verbose_name_plural = "Soportes a Clientes"
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['estado']),
            models.Index(fields=['fecha_leido']),
            models.Index(fields=['fecha_creacion']),
        ]
    
    def __str__(self):
        if self.contrato:
            cliente = self.contrato.nombre_completo
        elif self.cliente_externo:
            cliente = self.cliente_externo.nombre_completo
        else:
            cliente = "Cliente sin identificar"
        estado_display = self.get_estado_display()
        return f"Soporte #{self.id} - {cliente} [{estado_display}]"
    
    @property
    def nombre_cliente(self):
        if self.contrato:
            return self.contrato.nombre_completo
        elif self.cliente_externo:
            return self.cliente_externo.nombre_completo
        return "N/A"
    
    @property
    def fue_leido(self):
        """Indica si el soporte ya fue leído (estado LEIDO)"""
        return self.estado == self.EstadoSoporte.LEIDO
    
    def marcar_como_leido(self):
        """Marca el soporte como leído con la fecha actual"""
        if self.estado == self.EstadoSoporte.NO_LEIDO:
            from django.utils import timezone
            self.estado = self.EstadoSoporte.LEIDO
            self.fecha_leido = timezone.now()
            self.save(update_fields=['estado', 'fecha_leido'])
    
    def marcar_como_no_leido(self):
        """Marca el soporte como no leído"""
        if self.estado != self.EstadoSoporte.NO_LEIDO:
            self.estado = self.EstadoSoporte.NO_LEIDO
            self.fecha_leido = None
            self.save(update_fields=['estado', 'fecha_leido'])



class LeadInteresado(models.Model):
    """Leads que llegan del landing page (interesados en internet)"""
    
    class EstadoLead(models.TextChoices):
        NUEVO = 'NUEVO', '🆕 Nuevo (sin contacto)'
        CONTACTADO = 'CONTACTADO', '📞 Contactado'
        EN_SEGUIMIENTO = 'EN_SEGUIMIENTO', '⏳ En seguimiento'
        CONVERTIDO = 'CONVERTIDO', '✅ Convertido a cliente'
        PERDIDO = 'PERDIDO', '❌ Perdido/No interesado'
    
    # Datos básicos
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    
    # Mensaje del cliente
    mensaje = models.TextField(max_length=1000, verbose_name="Mensaje", blank=True, null=True)
    
    # Estado del lead
    estado = models.CharField(
        max_length=20,
        choices=EstadoLead.choices,
        default=EstadoLead.NUEVO,
        verbose_name="Estado",
        db_index=True
    )
    
    # Referencia al cliente potencial si se convirtió
    cliente_potencial_convertido = models.OneToOneField(
        'ClientePotencial',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='lead_origen',
        verbose_name="Cliente potencial convertido"
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")
    fecha_contactado = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de contacto")
    
    # Call center que lo contactó
    contactado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name='leads_contactados',
        verbose_name="Contactado por"
    )
    
    # Notas del call center
    notas_seguimiento = models.TextField(max_length=500, blank=True, null=True, verbose_name="Notas de seguimiento")
    
    class Meta:
        verbose_name = "Lead Interesado (Web)"
        verbose_name_plural = "Leads Interesados (Web)"
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['estado']),
            models.Index(fields=['fecha_creacion']),
            models.Index(fields=['telefono']),
        ]
    
    def __str__(self):
        return f"{self.nombre} - {self.telefono} [{self.get_estado_display()}]"
    
    def marcar_contactado(self, usuario):
        """Marca el lead como contactado"""
        from django.utils import timezone
        self.estado = self.EstadoLead.CONTACTADO
        self.fecha_contactado = timezone.now()
        self.contactado_por = usuario
        self.save(update_fields=['estado', 'fecha_contactado', 'contactado_por'])
    
    def convertir_a_cliente_potencial(self, cliente_potencial):
        """Convierte el lead en un cliente potencial"""
        self.cliente_potencial_convertido = cliente_potencial
        self.estado = self.EstadoLead.CONVERTIDO
        self.save(update_fields=['cliente_potencial_convertido', 'estado'])            