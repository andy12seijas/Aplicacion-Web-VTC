import re
from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm

from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import *


class UsuarioForm(forms.ModelForm):
    """Formulario para crear y editar usuarios con cedula y telefono"""
    
    # ===== CAMPOS EN EL MISMO ORDEN QUE LA TEMPLATE =====
    
    # 1. Cedula (primero en la template)
    cedula = forms.IntegerField(
        label='Cedula de Identidad',
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 12345678',
            'id': 'id_cedula'
        }),
        required=True
    )
    
    # 2. Usuario (segundo en la template)
    username = forms.CharField(
        label='Usuario',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Nombre de usuario',
            'id': 'id_username'
        }),
        required=True
    )
    
    # 3. Nombres (tercero en la template)
    first_name = forms.CharField(
        label='Nombres',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Nombres',
            'id': 'id_first_name'
        }),
        required=False
    )
    
    # 4. Apellidos (cuarto en la template)
    last_name = forms.CharField(
        label='Apellidos',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Apellidos',
            'id': 'id_last_name'
        }),
        required=False
    )
    
    # 5. Email (quinto en la template)
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'correo@ejemplo.com',
            'id': 'id_email'
        }),
        required=True
    )
    
    # 6. Telefono (sexto en la template)
    telefono = forms.CharField(
        label='Telefono',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 0412-1234567',
            'id': 'id_telefono'
        }),
        required=True,
        help_text="Ej: 0412-1234567"
    )
    
    # 7. Rol (despues en la template)
    rol = forms.ChoiceField(
        choices=[
            ('', 'Seleccionar rol'),
            ('Administrador', 'Administrador'),
            ('Vendedor', 'Vendedor'),
            ('Instalador', 'Instalador'),
            ('Supervisor', 'Supervisor'),
        ],
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_rol'
        })
    )
    
    # 8. Contrasena (campos al final)
    password1 = forms.CharField(
        label='Contrasena',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Contrasena',
            'id': 'id_password1'
        }),
        required=False
    )
    
    # 9. Confirmar contrasena
    password2 = forms.CharField(
        label='Confirmar contrasena',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirmar contrasena',
            'id': 'id_password2'
        }),
        required=False
    )
    
    class Meta:
        model = User
        # Especificamos explicitamente los campos en el orden correcto
        fields = ['username', 'email', 'first_name', 'last_name']
    
    def __init__(self, *args, **kwargs):
        self.es_creacion = kwargs.pop('es_creacion', True)
        super().__init__(*args, **kwargs)
        
        # DEBUG: Ver que campos tiene el formulario (SIN EMOJIS)
        print(f"DEBUG: CAMPOS DEL FORMULARIO: {list(self.fields.keys())}")
        
        # Reordenar los campos para que coincidan con la template
        field_order = ['cedula', 'username', 'first_name', 'last_name', 'email', 'telefono', 'rol', 'password1', 'password2']
        self.order_fields(field_order)
        
        # Si es edicion, cargar datos del perfil
        if not self.es_creacion and self.instance.pk:
            # Cargar rol actual
            grupos = self.instance.groups.all()
            if grupos:
                self.fields['rol'].initial = grupos[0].name
            
            # Cargar cedula y telefono del perfil
            try:
                perfil = self.instance.perfil
                self.fields['cedula'].initial = perfil.cedula
                self.fields['telefono'].initial = perfil.telefono
                
                self.fields['cedula'].widget.attrs['readonly'] = True
                self.fields['cedula'].widget.attrs['class'] = 'form-input readonly-field'
                self.fields['cedula'].help_text = 'La cedula no se puede modificar'
            except PerfilUsuario.DoesNotExist:
                # Si no existe perfil, lo creamos
                PerfilUsuario.objects.create(usuario=self.instance)
        
        # Configurar campos de contrasena segun sea creacion o edicion
        if not self.es_creacion:
            self.fields['password1'].required = False
            self.fields['password2'].required = False
            self.fields['password1'].help_text = 'Dejar en blanco para mantener la contrasena actual'
    
    def clean_cedula(self):
        cedula = self.cleaned_data.get('cedula')
        
        if self.es_creacion:
            # En creacion, verificar que la cedula no exista
            if PerfilUsuario.objects.filter(cedula=cedula).exists():
                raise forms.ValidationError('Esta cedula ya esta registrada.')
        else:
            # En edicion, verificar que la cedula no exista en OTRO usuario
            if PerfilUsuario.objects.filter(cedula=cedula).exclude(usuario=self.instance).exists():
                raise forms.ValidationError('Esta cedula ya esta registrada por otro usuario.')
        
        return cedula
    
    def clean(self):
        cleaned_data = super().clean()
        
        if self.es_creacion:
            password1 = cleaned_data.get('password1')
            password2 = cleaned_data.get('password2')
            
            if not password1:
                self.add_error('password1', 'Este campo es requerido.')
            if not password2:
                self.add_error('password2', 'Este campo es requerido.')
            if password1 and password2 and password1 != password2:
                self.add_error('password2', 'Las contrasenas no coinciden.')
        else:
            password1 = cleaned_data.get('password1')
            password2 = cleaned_data.get('password2')
            
            if password1 or password2:
                if password1 != password2:
                    self.add_error('password2', 'Las contrasenas no coinciden.')
        
        return cleaned_data
    
    def save(self, commit=True):
        # Guardar el usuario primero
        user = super().save(commit=False)
        
        # Establecer contrasena si es creacion o se proporciono una nueva
        if self.es_creacion or self.cleaned_data.get('password1'):
            user.set_password(self.cleaned_data['password1'])
        
        if commit:
            user.save()  # Guardar usuario
            
            # ===== AHORA GUARDAR EL PERFIL =====
            perfil, created = PerfilUsuario.objects.get_or_create(usuario=user)
            perfil.cedula = self.cleaned_data['cedula']
            perfil.telefono = self.cleaned_data['telefono']
            perfil.save()
            
            # LOG PARA VERIFICAR (SIN EMOJIS)
            print(f"INFO: Perfil guardado - Usuario={user.username}, Cedula={perfil.cedula}, Telefono={perfil.telefono}")
            # ===================================
            
            # Manejar grupos (roles)
            user.groups.clear()
            rol = self.cleaned_data.get('rol')
            if rol:
                try:
                    group = Group.objects.get(name=rol)
                    user.groups.add(group)
                    print(f"INFO: Rol '{rol}' asignado a {user.username}")
                except Group.DoesNotExist:
                    print(f"ERROR: Grupo '{rol}' no existe")
                    pass
            
            # Configurar is_staff segun el rol
            if not user.is_superuser:
                user.is_staff = (rol == 'Administrador')
                user.save()
        
        return user
    
    
    
from django import forms
from .models import ClientePotencial

class ClientePotencialForm(forms.ModelForm):
    """Formulario para crear y editar clientes potenciales"""
    
    class Meta:
        model = ClientePotencial
        fields = ['cedula', 'nombre', 'apellido', 'direccion', 'telefono',
                 'posee_internet', 'interesado', 'observacion', 'fecha_registro']
        widgets = {
            'cedula': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: 12345678',
                'autofocus': True,
                'min': 1
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: Juan'
            }),
            'apellido': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: Pérez'
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Calle, número, ciudad, etc.',
                'rows': 2
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '0412-1234567'
            }),
            'posee_internet': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            }),
            'interesado': forms.Select(attrs={
                'class': 'form-select'
            }),
            'observacion': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Notas adicionales sobre el cliente...',
                'rows': 3
            }),
            'fecha_registro': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'latitud': forms.HiddenInput(),
            'longitud': forms.HiddenInput(),
            'ubicacion_timestamp': forms.HiddenInput(),
        }
        labels = {
            'cedula': 'Cédula de Identidad',
            'posee_internet': '¿Ya tiene servicio de internet?',
            'interesado': 'Nivel de interés',
            'fecha_registro': 'Fecha de registro',
        }
        help_texts = {
            'cedula': 'Ingrese solo números, sin puntos ni letras',
            'telefono': 'Ej: 0412-1234567',
        }
    
    def __init__(self, *args, **kwargs):
        self.es_creacion = kwargs.pop('es_creacion', True)
        super().__init__(*args, **kwargs)
        
        # Si es edición, la cédula y fecha no deben ser editables
        if not self.es_creacion:
            self.fields['cedula'].disabled = True
            self.fields['fecha_registro'].disabled = True
            # INTERÉS E INTERNET SÍ SON EDITABLES - no los deshabilitamos
    
    def clean_cedula(self):
        cedula = self.cleaned_data.get('cedula')
        
        # En edición, no validar unicidad porque es el mismo cliente
        if not self.es_creacion:
            return cedula
        
        # En creación, validar que la cédula sea única
        if ClientePotencial.objects.filter(cedula=cedula).exists():
            raise forms.ValidationError('Esta cédula ya está registrada en el sistema.')
        return cedula



class ContratoClienteForm(forms.ModelForm):
    """Formulario para crear contratos de clientes - SIN CAMPOS DE PAGO"""
    
    class Meta:
        model = ContratoCliente
        # Excluir campos de pago y otros que no queremos
        exclude = [
            'ods', 'customer_id', 'atr', 'estado', 'cliente_potencial',
            'cedula', 'nombre', 'apellido', 'telefono_principal', 'creado_por',
             # 👈 ELIMINAMOS ESTOS CAMPOS
        ]
        widgets = {
            'otro_telefono': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: 0414-1234567'
            }),
            'correo_electronico': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'cliente@ejemplo.com'
            }),
            'direccion_detallada': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Calle, avenida, urbanización, casa/edificio, piso, apartamento',
                'rows': 3
            }),
            'fecha_nacimiento': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'plan_contratado': forms.Select(attrs={
                'class': 'form-select'
            }),
            'simple_plus': forms.Select(attrs={
                'class': 'form-select'
            }),
            'modalidad_equipo': forms.Select(attrs={
                'class': 'form-select'
            }),
            'punto_referencia': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: Cerca del abasto, frente a la farmacia'
            }),
            'tipo_vivienda': forms.Select(attrs={
                'class': 'form-select'
            }),
            'numero_casa': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: Casa #123, Edif. San José Piso 3 Apto 4'
            }),
            'red': forms.Select(attrs={
                'class': 'form-select'
            }),
             # 👇 AGREGAR LOS CAMPOS DE PAGO
            'numero_pago_movil': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: 0414-1234567',
                'maxlength': '20'
            }),
            'foto_pago': forms.FileInput(attrs={
                'class': 'form-file',
                'accept': 'image/*'
            }),
        }
        labels = {
            'otro_telefono': 'Otro Teléfono (opcional)',
            'correo_electronico': 'Correo Electrónico',
            'direccion_detallada': 'Dirección Detallada',
            'fecha_nacimiento': 'Fecha de Nacimiento',
            'plan_contratado': 'Plan a Contratar',
            'simple_plus': '¿Tiene Simple Plus?',
            'modalidad_equipo': 'Modalidad del Equipo',
            'punto_referencia': 'Punto de Referencia',
            'tipo_vivienda': 'Tipo de Vivienda',
            'numero_casa': 'Número de Casa/Edificio',
            'red': 'Red',
            'numero_pago_movil': 'Número de Pago Móvil ',
            'foto_pago': 'Foto del Comprobante de Pago ',
        }
    
    def clean_correo_electronico(self):
        """Validar que el correo no exista en OTRO contrato"""
        correo = self.cleaned_data.get('correo_electronico')
        
        # Validar formato básico de email
        if correo and ('@' not in correo or '.' not in correo):
            raise forms.ValidationError('Ingrese un correo electrónico válido.')
        
        # Si es edición, excluir el contrato actual
        if self.instance and self.instance.pk:
            if ContratoCliente.objects.filter(correo_electronico=correo).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError(
                    'Este correo electrónico ya está registrado en otro contrato. '
                    'Cada contrato debe tener un correo único.'
                )
        else:
            # Si es creación, verificar que no exista en ningún contrato
            if ContratoCliente.objects.filter(correo_electronico=correo).exists():
                raise forms.ValidationError(
                    'Este correo electrónico ya está registrado en otro contrato. '
                    'Cada contrato debe tener un correo único.'
                )
        
        return correo
    
    def __init__(self, *args, **kwargs):
        self.cliente_potencial = kwargs.pop('cliente_potencial', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar solo elementos activos
        self.fields['plan_contratado'].queryset = Plan.objects.filter(activo=True)
        self.fields['modalidad_equipo'].queryset = ModalidadEquipo.objects.filter(activo=True)
        self.fields['tipo_vivienda'].queryset = TipoVivienda.objects.filter(activo=True)
        self.fields['red'].queryset = Red.objects.filter(activo=True)
        
        # Hacer campos obligatorios
        self.fields['correo_electronico'].required = True
        self.fields['direccion_detallada'].required = True
        self.fields['fecha_nacimiento'].required = True
        self.fields['plan_contratado'].required = True
        self.fields['simple_plus'].required = True
        self.fields['modalidad_equipo'].required = True
        self.fields['punto_referencia'].required = True
        self.fields['tipo_vivienda'].required = True
        self.fields['numero_casa'].required = True
        self.fields['red'].required = True
        
from django import forms
from django.contrib.auth.models import Group, User
from .models import Cuadrilla, PerfilUsuario

class CuadrillaForm(forms.ModelForm):
    
    class Meta:
        model = Cuadrilla
        fields = [
            'nombre', 'codigo', 'instaladores', 'estado', 'activo'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: Cuadrilla Norte'
            }),
            'codigo': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: C001'
            }),
            # CAMBIAR SelectMultiple por CheckboxSelectMultiple
            'instaladores': forms.CheckboxSelectMultiple(attrs={
                'class': 'instaladores-checkbox'
            }),
            'estado': forms.Select(attrs={
                'class': 'form-select'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
                'checked': True
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        try:
            # Obtener el grupo de instaladores
            grupo_instalador = Group.objects.get(name='Instalador')
            
            # Obtener IDs de instaladores que ya están en otras cuadrillas
            instaladores_en_cuadrillas = PerfilUsuario.objects.filter(
                cuadrillas__isnull=False
            ).values_list('id', flat=True)
            
            # Si estamos editando, excluir los instaladores de esta cuadrilla
            if self.instance.pk:
                instaladores_de_esta_cuadrilla = self.instance.instaladores.values_list('id', flat=True)
                # Excluir instaladores que están en otras cuadrillas pero incluir los de esta
                instaladores_excluir = [id for id in instaladores_en_cuadrillas if id not in instaladores_de_esta_cuadrilla]
            else:
                # Para creación nueva, excluir todos los instaladores que ya están en alguna cuadrilla
                instaladores_excluir = instaladores_en_cuadrillas
            
            # Filtrar instaladores
            self.fields['instaladores'].queryset = PerfilUsuario.objects.filter(
                usuario__groups=grupo_instalador,
                usuario__is_active=True
            ).exclude(
                id__in=instaladores_excluir
            ).select_related('usuario').order_by('usuario__first_name')
            
        except Group.DoesNotExist:
            self.fields['instaladores'].queryset = PerfilUsuario.objects.none()
        
        # Personalizar etiquetas para CheckboxSelectMultiple
        self.fields['instaladores'].label_from_instance = self.instalador_label
        
        # Hacer campos obligatorios
        self.fields['nombre'].required = True
        self.fields['codigo'].required = True
    
    def instalador_label(self, obj):
        """Formato personalizado para mostrar instaladores"""
        nombre_completo = obj.usuario.get_full_name() or obj.usuario.username
        cedula = obj.cedula or 'Sin cédula'
        telefono = obj.telefono or 'Sin teléfono'
        return f"{nombre_completo} - {cedula} - {telefono}"
    
    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if codigo:
            codigo = codigo.upper()
            # Excluir la instancia actual si estamos editando
            queryset = Cuadrilla.objects.filter(codigo=codigo)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError('Ya existe una cuadrilla con este código')
        return codigo
    
    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if nombre:
            # Excluir la instancia actual si estamos editando
            queryset = Cuadrilla.objects.filter(nombre=nombre)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError('Ya existe una cuadrilla con este nombre')
        return nombre
    
    
from django import forms
from .models import AsignacionContrato, Cuadrilla

class AsignacionContratoForm(forms.ModelForm):
    class Meta:
        model = AsignacionContrato
        fields = ['cuadrilla', 'observaciones']
        widgets = {
            'cuadrilla': forms.Select(attrs={
                'class': 'form-select'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Observaciones adicionales...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuadrilla'].queryset = Cuadrilla.objects.filter(activo=True).order_by('nombre')
        self.fields['cuadrilla'].label = "Seleccionar Cuadrilla"
        self.fields['cuadrilla'].empty_label = "--- Seleccione una cuadrilla ---"  
        
        


from django import forms
from .models import Instalacion, ModeloModem

# forms.py

from django import forms
from .models import Instalacion, ModeloModem

class MultipleFileInput(forms.ClearableFileInput):
    """Widget personalizado para permitir múltiples archivos"""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Campo personalizado para manejar múltiples archivos"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={
            'multiple': True,
            'accept': 'image/*',
            'class': 'form-file',
            'id': 'id_fotos'
        }))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # Si no se subieron archivos, devolver lista vacía
        if not data:
            return []
        
        # Si es una lista de archivos, validar cada uno
        if isinstance(data, list):
            valid_files = []
            for file in data:
                # Validar cada archivo individualmente
                if file:
                    try:
                        # Validar el archivo usando el método clean del padre
                        cleaned_file = super().clean(file, initial)
                        valid_files.append(cleaned_file)
                    except forms.ValidationError as e:
                        # Si hay error, lo añadimos a los errores del campo
                        if hasattr(self, 'field'):
                            self.field.add_error(e)
                        raise
            return valid_files
        else:
            # Si es un solo archivo
            return [super().clean(data, initial)] if data else []


class InstalacionForm(forms.ModelForm):
    """Formulario para registrar instalación"""
    
    fotos = MultipleFileField(
        required=False,
        help_text="Puede seleccionar múltiples fotos (JPG, PNG)"
    )
    
    class Meta:
        model = Instalacion
        fields = [
            'latitud', 'longitud',
            'feeder', 'caja', 'puerto_utilizado',
            'modelo_modem', 'sn_modem', 'mac_modem',
            'inicio_fibra', 'final_fibra',
            'conectores', 'rosetas', 'patch_cord', 'tensores', 'conectores_malos',
            'observacion'
        ]
        widgets = {
            'latitud': forms.NumberInput(attrs={
                'class': 'form-input', 
                'step': '0.000001', 
                'placeholder': '10.126830',
                
                'id': 'id_latitud'
            }),
            'longitud': forms.NumberInput(attrs={
                'class': 'form-input', 
                'step': '0.000001', 
                'placeholder': '-68.009860',
                
                'id': 'id_longitud'
            }),
            'feeder': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': 'Ej: FVL01'
            }),
            'caja': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': 'Ej: N0101'
            }),
            'puerto_utilizado': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': 'Ej: 3'
            }),
            'modelo_modem': forms.Select(attrs={
                'class': 'form-select'
            }),
            'sn_modem': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': 'Ej: ALCLFCD0A4C5'
            }),
            'mac_modem': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': 'Ej: E8F8D0BC1560'
            }),
            'inicio_fibra': forms.NumberInput(attrs={
                'class': 'form-input', 
                'placeholder': '35',
                'min': '0'
            }),
            'final_fibra': forms.NumberInput(attrs={
                'class': 'form-input', 
                'placeholder': '5',
                'min': '0'
            }),
            'conectores': forms.NumberInput(attrs={
                'class': 'form-input', 
                'value': 0,
                'min': '0'
            }),
            'rosetas': forms.NumberInput(attrs={
                'class': 'form-input', 
                'value': 0,
                'min': '0'
            }),
            'patch_cord': forms.NumberInput(attrs={
                'class': 'form-input', 
                'value': 0,
                'min': '0'
            }),
            'tensores': forms.NumberInput(attrs={
                'class': 'form-input', 
                'value': 0,
                'min': '0'
            }),
            'conectores_malos': forms.NumberInput(attrs={
                'class': 'form-input', 
                'value': 0,
                'min': '0'
            }),
            'observacion': forms.Textarea(attrs={
                'class': 'form-input', 
                'rows': 3, 
                'placeholder': 'Observaciones adicionales...'
            }),
        }
        labels = {
            'latitud': 'LATITUD',
            'longitud': 'LONGITUD',
            'feeder': 'FEEDER',
            'caja': 'CAJA',
            'puerto_utilizado': 'PUERTO UTILIZADO',
            'modelo_modem': 'MODELO',
            'sn_modem': 'SERIAL',
            'mac_modem': 'MAC',
            'inicio_fibra': 'INICIO',
            'final_fibra': 'FINAL',
            'conectores': 'CONECTORES',
            'rosetas': 'ROSETAS',
            'patch_cord': 'PACH CORD',
            'tensores': 'TENSORES',
            'conectores_malos': 'CONECTORES MALOS',
            'observacion': 'OBSERVACIÓN',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configurar queryset para modelo_modem
        self.fields['modelo_modem'].queryset = ModeloModem.objects.filter(activo=True)
        self.fields['modelo_modem'].empty_label = "--- Seleccione un modelo ---"
        
        # Hacer que latitud y longitud no sean requeridos
        self.fields['latitud'].required = False
        self.fields['longitud'].required = False
        
        # Hacer que los campos numéricos tengan valor por defecto 0
        for field_name in ['conectores', 'rosetas', 'patch_cord', 'tensores', 'conectores_malos']:
            if field_name in self.fields:
                self.fields[field_name].initial = 0
                self.fields[field_name].required = False
    
    def clean(self):
        """Validaciones personalizadas"""
        cleaned_data = super().clean()
        
        # Validar que si hay inicio_fibra, también haya final_fibra
        inicio = cleaned_data.get('inicio_fibra')
        final = cleaned_data.get('final_fibra')
        
        if inicio is not None and final is None:
            self.add_error('final_fibra', 'Debe ingresar el valor FINAL')
        elif final is not None and inicio is None:
            self.add_error('inicio_fibra', 'Debe ingresar el valor INICIO')
        
        # Validar que los valores numéricos no sean negativos
        for field_name in ['conectores', 'rosetas', 'patch_cord', 'tensores', 'conectores_malos']:
            value = cleaned_data.get(field_name)
            if value is not None and value < 0:
                self.add_error(field_name, 'El valor no puede ser negativo')
        
        return cleaned_data


class VentaDirectaForm(forms.ModelForm):
    """Formulario para crear/editar ventas directas"""
    
    class Meta:
        model = VentaDirecta
        fields = [
            'nro_orden', 'cedula', 'customer_id', 'nombre', 'apellido',
            'telefono', 'plan', 'observacion'
        ]
        widgets = {
            'nro_orden': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: ORD-001',
                'required': True
            }),
            'cedula': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: 12345678',
                'required': True
            }),
            'customer_id': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: CUS-123456',
                'required': True
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nombre del cliente',
                'required': True
            }),
            'apellido': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Apellido del cliente',
                'required': True
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: 0412-1234567',
                'required': True
            }),
            'plan': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'observacion': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Notas adicionales sobre la venta...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['plan'].queryset = Plan.objects.filter(activo=True)
        self.fields['plan'].empty_label = "Seleccione un plan"
    
    def clean_nro_orden(self):
        """Validar que el número de orden no esté duplicado"""
        nro_orden = self.cleaned_data.get('nro_orden')
        if nro_orden:
            instance = getattr(self, 'instance', None)
            if instance and instance.pk:
                if VentaDirecta.objects.filter(nro_orden=nro_orden).exclude(pk=instance.pk).exists():
                    raise forms.ValidationError('Este número de orden ya existe.')
            else:
                if VentaDirecta.objects.filter(nro_orden=nro_orden).exists():
                    raise forms.ValidationError('Este número de orden ya existe.')
        return nro_orden
    
    def clean_customer_id(self):
        """Validar que customer_id sea obligatorio"""
        customer_id = self.cleaned_data.get('customer_id')
        if not customer_id:
            raise forms.ValidationError('El Customer ID es obligatorio.')
        return customer_id


class CambiarEstadoVentaForm(forms.Form):
    """Formulario para cambiar estado de una venta directa"""
    estado = forms.ChoiceField(
        choices=VentaDirecta.EstadoVenta.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )    
    
    
class SoporteForm(forms.ModelForm):
    """Formulario para crear/editar soportes"""
    
    # Campo para múltiples fotos
    fotos_upload = MultipleFileField(
        required=False,
        label="Fotos del soporte",
        help_text="Puedes seleccionar múltiples imágenes (JPG, PNG, GIF - Máx. 5MB cada una)"
    )
    
    class Meta:
        model = Soporte
        fields = [
            'instalacion', 'tipo', 'fecha_hora_servicio',
            'falla_encontrada', 'solucion',
            'modelo_modem', 'sn_modem', 'mac_modem',  # ← NUEVOS CAMPOS
            'inicio_fibra', 'final_fibra',
            'conectores', 'rosetas', 'patch_cord', 'tensores', 'conectores_malos',
            'pin_ubicacion_lat', 'pin_ubicacion_lng',
            'puerto_nap_utilizado', 'caja_nap_utilizada',
            'observaciones'
        ]
        widgets = {
            'instalacion': forms.HiddenInput(),
            'tipo': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipo'}),
            'fecha_hora_servicio': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'falla_encontrada': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Describa brevemente la falla encontrada...'}),
            'solucion': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Describa brevemente la solución aplicada...'}),
            'modelo_modem': forms.Select(attrs={'class': 'form-control'}),  # ← NUEVO
            'sn_modem': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Serial del módem (Ej: ABC123XYZ)'}),  # ← NUEVO
            'mac_modem': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'MAC Address (Ej: 00:1A:2B:3C:4D:5E)'}),  # ← NUEVO
            'inicio_fibra': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 100'}),
            'final_fibra': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 115'}),
            'conectores': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad de conectores usados'}),
            'rosetas': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad de rosetas usadas'}),
            'patch_cord': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad de patch cord usados'}),
            'tensores': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad de tensores usados'}),
            'conectores_malos': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad de conectores malos'}),
            'pin_ubicacion_lat': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Ej: 10.123456', 'id': 'id_pin_lat'}),
            'pin_ubicacion_lng': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Ej: -66.123456', 'id': 'id_pin_lng'}),
            'puerto_nap_utilizado': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: P1, P2, P3...'}),
            'caja_nap_utilizada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: CAJA-001, NAP-002...'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Observaciones adicionales...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si es edición, cargar las fotos existentes
        if self.instance and self.instance.pk and self.instance.fotos:
            self.initial['fotos_upload'] = self.instance.fotos
        
        # Filtrar solo modelos activos
        from myapp.models import ModeloModem
        self.fields['modelo_modem'].queryset = ModeloModem.objects.filter(activo=True)
        self.fields['modelo_modem'].empty_label = "Seleccione un modelo"
    
    def clean_mac_modem(self):
        """Validar formato de MAC address"""
        mac = self.cleaned_data.get('mac_modem')
        if mac:
            import re
            # Formato MAC: XX:XX:XX:XX:XX:XX o XX-XX-XX-XX-XX-XX
            pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
            if not re.match(pattern, mac):
                raise forms.ValidationError('Formato de MAC inválido. Use formato XX:XX:XX:XX:XX:XX')
            # Normalizar a mayúsculas
            mac = mac.upper()
        return mac
    
    def clean(self):
        cleaned_data = super().clean()
        inicio_fibra = cleaned_data.get('inicio_fibra')
        final_fibra = cleaned_data.get('final_fibra')
        
        if inicio_fibra and final_fibra and inicio_fibra <= final_fibra:
            self.add_error('final_fibra', 'El valor FINAL debe ser menos que el  INICIO')
        
        # Validar que si se ingresa latitud, también se ingrese longitud
        pin_lat = cleaned_data.get('pin_ubicacion_lat')
        pin_lng = cleaned_data.get('pin_ubicacion_lng')
        
        if pin_lat and not pin_lng:
            self.add_error('pin_ubicacion_lng', 'Debe ingresar la longitud junto con la latitud')
        if pin_lng and not pin_lat:
            self.add_error('pin_ubicacion_lat', 'Debe ingresar la latitud junto con la longitud')
        
        return cleaned_data
    
    def save(self, commit=True):
        soporte = super().save(commit=False)
        
        if commit:
            soporte.save()
            self.save_m2m()
            
            # Procesar las fotos subidas
            fotos = self.cleaned_data.get('fotos_upload', [])
            if fotos:
                fotos_urls = []
                from django.core.files.storage import default_storage
                import os
                from django.utils import timezone
                
                for foto in fotos:
                    # Guardar foto
                    extension = os.path.splitext(foto.name)[1].lower()
                    nombre_archivo = f"soporte_{soporte.id}_{timezone.now().timestamp()}{extension}"
                    ruta = os.path.join('soportes', nombre_archivo)
                    
                    saved_path = default_storage.save(ruta, foto)
                    fotos_urls.append(default_storage.url(saved_path))
                
                # Actualizar el campo fotos del soporte
                if soporte.fotos:
                    soporte.fotos.extend(fotos_urls)
                else:
                    soporte.fotos = fotos_urls
                soporte.save()
        
        return soporte

class SoporteFotosForm(forms.Form):
    """Formulario para subir fotos adicionales al soporte"""
    fotos = MultipleFileField(
        required=False,
        label="Agregar más fotos"
    )
    
    
    
class SoporteEditarForm(forms.ModelForm):
    """Formulario específico para EDITAR soportes (estos campos no se modifican)"""
    
    # Campo para múltiples fotos NUEVAS (no afecta las existentes)
    fotos_upload = MultipleFileField(
        required=False,
        label="Agregar más fotos",
        help_text="Puedes seleccionar múltiples imágenes (JPG, PNG, GIF - Máx. 5MB cada una)"
    )
    
    class Meta:
        model = Soporte
        # EXCLUIMOS los campos que NO deben modificarse en edición
        exclude = [
            'instalacion',      # No se puede cambiar la instalación original
            'tipo',             # No se puede cambiar el tipo de soporte
            'estado',           # El estado se maneja aparte
            'instaladores',     # Los instaladores que realizaron el soporte
            'fotos',            # Las fotos se manejan aparte (solo se agregan)
            'creado_por',       # Quién lo creó
            'fecha_creacion',   # Fecha de creación
            'fecha_actualizacion' # Se actualiza automáticamente
        ]
        widgets = {
            'fecha_hora_servicio': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'falla_encontrada': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Describa brevemente la falla encontrada...'}),
            'solucion': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Describa brevemente la solución aplicada...'}),
            'modelo_modem': forms.Select(attrs={'class': 'form-control'}),
            'sn_modem': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Serial del módem (Ej: ABC123XYZ)'}),
            'mac_modem': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'MAC Address (Ej: 00:1A:2B:3C:4D:5E)'}),
            'inicio_fibra': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 100'}),
            'final_fibra': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 85'}),
            'conectores': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad de conectores usados'}),
            'rosetas': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad de rosetas usadas'}),
            'patch_cord': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad de patch cord usados'}),
            'tensores': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad de tensores usados'}),
            'conectores_malos': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad de conectores malos'}),
            'pin_ubicacion_lat': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Ej: 10.123456', 'id': 'id_pin_lat'}),
            'pin_ubicacion_lng': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Ej: -66.123456', 'id': 'id_pin_lng'}),
            'puerto_nap_utilizado': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: P1, P2, P3...'}),
            'caja_nap_utilizada': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: CAJA-001, NAP-002...'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Observaciones adicionales...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrar solo modelos activos
        self.fields['modelo_modem'].queryset = ModeloModem.objects.filter(activo=True)
        self.fields['modelo_modem'].empty_label = "Seleccione un modelo"
    
    def clean_mac_modem(self):
        """Validar formato de MAC address"""
        mac = self.cleaned_data.get('mac_modem')
        if mac:
            pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
            if not re.match(pattern, mac):
                raise forms.ValidationError('Formato de MAC inválido. Use formato XX:XX:XX:XX:XX:XX')
            mac = mac.upper()
        return mac
    
    def clean(self):
        cleaned_data = super().clean()
        inicio_fibra = cleaned_data.get('inicio_fibra')
        final_fibra = cleaned_data.get('final_fibra')
        
        if inicio_fibra is not None and final_fibra is not None:
            # FINAL debe ser MENOR o IGUAL que INICIO
            if final_fibra > inicio_fibra:
                self.add_error('final_fibra', 'Los metros finales no pueden ser mayores que los metros iniciales')
        
        # Validar coordenadas
        pin_lat = cleaned_data.get('pin_ubicacion_lat')
        pin_lng = cleaned_data.get('pin_ubicacion_lng')
        
        if pin_lat and not pin_lng:
            self.add_error('pin_ubicacion_lng', 'Debe ingresar la longitud junto con la latitud')
        if pin_lng and not pin_lat:
            self.add_error('pin_ubicacion_lat', 'Debe ingresar la latitud junto con la longitud')
        
        return cleaned_data
    
    def save(self, commit=True):
        """Guardar solo los campos editables, preservando los demás"""
        soporte = super().save(commit=False)
        
        # NO modificamos: estado, instaladores, fotos (solo se agregan nuevas)
        
        if commit:
            soporte.save()
            self.save_m2m()
        
        return soporte
    
    
    
class InstalacionEditForm(forms.ModelForm):
    """Formulario para editar instalaciones"""
    
    fotos_upload = MultipleFileField(
        required=False,
        label="Agregar más fotos",
        help_text="Puedes seleccionar múltiples imágenes (JPG, PNG, GIF - Máx. 5MB cada una)"
    )
    
    class Meta:
        model = Instalacion
        fields = [
            'latitud', 'longitud', 'feeder', 'caja', 'puerto_utilizado',
            'modelo_modem', 'sn_modem', 'mac_modem',
            'inicio_fibra', 'final_fibra',
            'conectores', 'rosetas', 'patch_cord', 'tensores', 'conectores_malos',
            'observacion', 'completada'
        ]
        widgets = {
            'latitud': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Ej: 10.123456'}),
            'longitud': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'Ej: -66.123456'}),
            'feeder': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: FEEDER-001'}),
            'caja': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: CAJA-001'}),
            'puerto_utilizado': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: P1'}),
            'modelo_modem': forms.Select(attrs={'class': 'form-control'}),
            'sn_modem': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Serial del módem'}),
            'mac_modem': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'MAC Address'}),
            'inicio_fibra': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Metros iniciales'}),
            'final_fibra': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Metros finales'}),
            'conectores': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad'}),
            'rosetas': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad'}),
            'patch_cord': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad'}),
            'tensores': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad'}),
            'conectores_malos': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Cantidad'}),
            'observacion': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Observaciones...'}),
            'completada': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['modelo_modem'].queryset = ModeloModem.objects.filter(activo=True)
        self.fields['modelo_modem'].empty_label = "Seleccione un modelo"
    
           