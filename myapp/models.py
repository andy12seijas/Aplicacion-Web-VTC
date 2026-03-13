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