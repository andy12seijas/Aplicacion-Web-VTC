from pathlib import Path
import os

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'mnejv+1neoy#utf^le812j(n8bznl!#s*q4*1fi1dtj=4c-)*i'

DEBUG = False

# ⬅️ AGREGADO vtconexiones.com
ALLOWED_HOSTS = [
    'vtconexiones.com',
    'www.vtconexiones.com',
    'localhost',
    '127.0.0.1',
    '.onrender.com',
]

# ⬅️ AGREGADO CSRF para Namecheap
CSRF_TRUSTED_ORIGINS = [
    'https://vtconexiones.com',
    'https://www.vtconexiones.com',
    'https://aplicacion-web-vtc-2.onrender.com',
    'http://localhost:8000',
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'myapp'
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'myapp.middleware.ZonaHorariaMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
]

# URLs de autenticación
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# Media files
MEDIA_URL = '/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'pagos')

# URL configuration
ROOT_URLCONF = 'mysite.urls'

# Static files (CSS, JavaScript, Images) - ⬅️ CORREGIDO (solo una vez)
STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'myapp.context_processors.zona_horaria_venezuela',
            ],
        },
    },
]

WSGI_APPLICATION = 'mysite.wsgi.application'

# Database
"""DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}"""

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'vtcodcnb_miapp_db',
        'USER': 'vtcodcnb_admin',
        'PASSWORD': 'Simple2026**',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',  # 🔒 Mejor para seguridad y caracteres
            'use_unicode': True,   # 🔒 Manejo seguro de strings
        },
        # 🔒 Timeout para evitar conexiones huérfanas
        'CONN_MAX_AGE': 600,
        # 🔒 Número de intentos de reconexión
        'CONN_HEALTH_CHECKS': True,
    }
}

# Seguridad adicional
SECURE_BROWSER_XSS_FILTER = True  # 🔒 Protección XSS
SECURE_CONTENT_TYPE_NOSNIFF = True  # 🔒 Evita MIME sniffing
X_FRAME_OPTIONS = 'DENY'  # 🔒 Anti-clickjacking

# Si usas HTTPS (recomendado)
CSRF_COOKIE_SECURE = True  # Solo enviar CSRF por HTTPS
SESSION_COOKIE_SECURE = True  # Solo enviar sesión por HTTPS
SECURE_SSL_REDIRECT = True  # Redirigir HTTP a HTTPS
SECURE_HSTS_SECONDS = 31536000  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'es-ve'  # o 'en-us'
USE_I18N = True

# ⚠️ IMPORTANTE: Esto debe estar EXACTAMENTE así
TIME_ZONE = 'America/Caracas'

# Esto debe ser True
USE_TZ = True
# Django usará la zona horaria de Venezuela automáticamente

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'