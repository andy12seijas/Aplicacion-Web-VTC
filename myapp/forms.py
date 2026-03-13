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