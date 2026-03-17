from django.urls import path
from myapp.views_login import * 
from myapp.views_admin import *
from myapp.views_vendedores import *
from . import views_vendedores
from django.contrib.auth.decorators import user_passes_test

def es_admin_o_superuser(user):
    return user.is_superuser or user.groups.filter(name='Administrador').exists()

urlpatterns = [
    #URLS DE INICIO
    path('', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
    #URLS DE ADMINISTRACION
    path('lista_usuarios/', lista_usuarios, name='lista_usuarios'),
    path('crear_usuario/', crear_usuario, name='crear_usuario'),
    path('usuario/<int:user_id>/editar',editar_usuario,name='editar_usuario'),
    path('mapa-usuarios/',mapa_usuarios, name='mapa_usuarios'),
    path('api/ubicaciones/', api_ubicaciones, name='api_ubicaciones'),
    path('panel-admin/', panel_administrativo, name='panel_administrativo'),
    path('administrador/contratos/', gestionar_contratos, name='gestionar_contratos'),
    path('contrato/<int:contrato_id>/completar/', completar_contrato, name='completar_contrato'),
    #URLS DE VENDEDORES
    path('lista_clientes/', lista_clientes, name='lista_clientes'),
    path('crear_cliente/', crear_cliente, name='crear_cliente'),
    path('cliente/<int:cliente_id>/editar/',user_passes_test(es_admin_o_superuser, login_url='lista_clientes')(editar_cliente),name='editar_cliente'),
    path('verificar-cedula/<int:cedula>/', verificar_cedula, name='verificar_cedula'),
    path('cliente/<int:cliente_id>/datos/', datos_cliente, name='datos_cliente'),
    path('verificar-cliente-contrato/<int:cedula>/', verificar_cliente_contrato, name='verificar_cliente_contrato'),
    path('contrato/crear/', crear_contrato, name='crear_contrato'),
    path('lista_contratos/', lista_contratos, name='lista_contratos'),
    path('datos-contrato/<int:contrato_id>/', datos_contrato, name='datos_contrato'),
    path('contrato/crear/error/', crear_contrato_error, name='crear_contrato_error'),
]


