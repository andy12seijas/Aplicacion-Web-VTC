from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm

from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import *


class UsuarioForm(forms.ModelForm):
    """Formulario para crear y editar usuarios con cédula y teléfono"""
    
    # ===== CAMPOS EN EL MISMO ORDEN QUE LA TEMPLATE =====
    
    # 1. Cédula (primero en la template)
    cedula = forms.IntegerField(
        label='Cédula de Identidad',
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
    
    # 6. Teléfono (sexto en la template)
    telefono = forms.CharField(
        label='Teléfono',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ej: 0412-1234567',
            'id': 'id_telefono'
        }),
        required=True,
        help_text="Ej: 0412-1234567"
    )
    
    # 7. Rol (después en la template)
    rol = forms.ChoiceField(
        choices=[
            ('', 'Seleccionar rol'),
            ('Administrador', 'Administrador'),
            ('Vendedor', 'Vendedor'),
            ('Instalador', 'Instalador'),
        ],
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_rol'
        })
    )
    
    # 8. Contraseña (campos al final)
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Contraseña',
            'id': 'id_password1'
        }),
        required=False
    )
    
    # 9. Confirmar contraseña
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirmar contraseña',
            'id': 'id_password2'
        }),
        required=False
    )
    
    class Meta:
        model = User
        # Especificamos explícitamente los campos en el orden correcto
        fields = ['username', 'email', 'first_name', 'last_name']
    
    def __init__(self, *args, **kwargs):
        self.es_creacion = kwargs.pop('es_creacion', True)
        super().__init__(*args, **kwargs)
        
        # DEBUG: Ver qué campos tiene el formulario
        print(f"📋 CAMPOS DEL FORMULARIO: {list(self.fields.keys())}")
        
        # Reordenar los campos para que coincidan con la template
        field_order = ['cedula', 'username', 'first_name', 'last_name', 'email', 'telefono', 'rol', 'password1', 'password2']
        self.order_fields(field_order)
        
        # Si es edición, cargar datos del perfil
        if not self.es_creacion and self.instance.pk:
            # Cargar rol actual
            grupos = self.instance.groups.all()
            if grupos:
                self.fields['rol'].initial = grupos[0].name
            
            # Cargar cédula y teléfono del perfil
            try:
                perfil = self.instance.perfil
                self.fields['cedula'].initial = perfil.cedula
                self.fields['telefono'].initial = perfil.telefono
                
                self.fields['cedula'].widget.attrs['readonly'] = True
                self.fields['cedula'].widget.attrs['class'] = 'form-input readonly-field'
                self.fields['cedula'].help_text = 'La cédula no se puede modificar'
            except PerfilUsuario.DoesNotExist:
                # Si no existe perfil, lo creamos
                PerfilUsuario.objects.create(usuario=self.instance)
        
        # Configurar campos de contraseña según sea creación o edición
        if not self.es_creacion:
            self.fields['password1'].required = False
            self.fields['password2'].required = False
            self.fields['password1'].help_text = 'Dejar en blanco para mantener la contraseña actual'
    
    def clean_cedula(self):
        cedula = self.cleaned_data.get('cedula')
        
        if self.es_creacion:
            # En creación, verificar que la cédula no exista
            if PerfilUsuario.objects.filter(cedula=cedula).exists():
                raise forms.ValidationError('Esta cédula ya está registrada.')
        else:
            # En edición, verificar que la cédula no exista en OTRO usuario
            if PerfilUsuario.objects.filter(cedula=cedula).exclude(usuario=self.instance).exists():
                raise forms.ValidationError('Esta cédula ya está registrada por otro usuario.')
        
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
                self.add_error('password2', 'Las contraseñas no coinciden.')
        else:
            password1 = cleaned_data.get('password1')
            password2 = cleaned_data.get('password2')
            
            if password1 or password2:
                if password1 != password2:
                    self.add_error('password2', 'Las contraseñas no coinciden.')
        
        return cleaned_data
    
    def save(self, commit=True):
        # Guardar el usuario primero
        user = super().save(commit=False)
        
        # Establecer contraseña si es creación o se proporcionó una nueva
        if self.es_creacion or self.cleaned_data.get('password1'):
            user.set_password(self.cleaned_data['password1'])
        
        if commit:
            user.save()  # Guardar usuario
            
            # ===== AHORA GUARDAR EL PERFIL =====
            perfil, created = PerfilUsuario.objects.get_or_create(usuario=user)
            perfil.cedula = self.cleaned_data['cedula']
            perfil.telefono = self.cleaned_data['telefono']
            perfil.save()
            
            # LOG PARA VERIFICAR
            print(f"✅ Perfil guardado: Usuario={user.username}, Cédula={perfil.cedula}, Teléfono={perfil.telefono}")
            # ===================================
            
            # Manejar grupos (roles)
            user.groups.clear()
            rol = self.cleaned_data.get('rol')
            if rol:
                try:
                    group = Group.objects.get(name=rol)
                    user.groups.add(group)
                    print(f"✅ Rol '{rol}' asignado a {user.username}")
                except Group.DoesNotExist:
                    print(f"❌ Grupo '{rol}' no existe")
                    pass
            
            # Configurar is_staff según el rol
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
            'instaladores': forms.SelectMultiple(attrs={
                'class': 'form-select instaladores-select',
                'style': 'width: 100%; min-height: 200px;'
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
        
        # Personalizar etiquetas
        self.fields['instaladores'].label_from_instance = self.instalador_label
        
        # Hacer campos obligatorios
        self.fields['nombre'].required = True
        self.fields['codigo'].required = True
    
    def instalador_label(self, obj):
        """Formato personalizado para mostrar instaladores"""
        nombre_completo = obj.usuario.get_full_name() or obj.usuario.username
        return f"{nombre_completo} - {obj.cedula or 'Sin cédula'} - {obj.telefono or 'Sin teléfono'}"
    
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

class InstalacionForm(forms.ModelForm):
    class Meta:
        model = Instalacion
        fields = [
            'feeder', 'caja', 'puerto_utilizado',
            'ubicacion_lat', 'ubicacion_lng',
            'modelo_modem', 'sn_modem', 'mac_modem',
            'inicio_fibra', 'final_fibra',
            'conectores', 'rosetas', 'patch_cord', 'tensores', 'conectores_malos',
            'observacion'
        ]
        widgets = {
            'feeder': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej: FVL01'}),
            'caja': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej: N0101'}),
            'puerto_utilizado': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej: 3'}),
            'ubicacion_lat': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.000001', 'placeholder': '10.126830'}),
            'ubicacion_lng': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.000001', 'placeholder': '-68.009860'}),
            'modelo_modem': forms.Select(attrs={'class': 'form-select'}),
            'sn_modem': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej: ALCLFCD0A4C5'}),
            'mac_modem': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ej: E8F8D0BC1560'}),
            'inicio_fibra': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '35'}),
            'final_fibra': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '5'}),
            'conectores': forms.NumberInput(attrs={'class': 'form-input', 'value': 0}),
            'rosetas': forms.NumberInput(attrs={'class': 'form-input', 'value': 0}),
            'patch_cord': forms.NumberInput(attrs={'class': 'form-input', 'value': 0}),
            'tensores': forms.NumberInput(attrs={'class': 'form-input', 'value': 0}),
            'conectores_malos': forms.NumberInput(attrs={'class': 'form-input', 'value': 0}),
            'observacion': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Observaciones adicionales...'}),
        }
        labels = {
            'feeder': 'FEEDER',
            'caja': 'CAJA',
            'puerto_utilizado': 'PUERTO UTILIZADO',
            'ubicacion_lat': 'Latitud',
            'ubicacion_lng': 'Longitud',
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
        self.fields['modelo_modem'].queryset = ModeloModem.objects.filter(activo=True)
        self.fields['modelo_modem'].empty_label = "--- Seleccione un modelo ---"          