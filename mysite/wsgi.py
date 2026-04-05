"""
WSGI config for mysite project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import sys

# Añade tu proyecto al path de Python
sys.path.append(os.path.dirname(__file__))

# Cambia 'tu_proyecto' por el nombre de la carpeta que tiene 'settings.py'
# En tu captura, esa carpeta se llama 'mysite'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
