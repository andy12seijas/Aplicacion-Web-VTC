from django.urls import path
from myapp.views_login import * 
from myapp.views_admin import *
from myapp.views_asignacion import *
from myapp.views_nomina import recalcular_nomina
from myapp.views_vendedores import *
from myapp.views_instaladores import *
from myapp.views_venta_directa import *
from django.contrib.auth.decorators import user_passes_test
from myapp.views_reporte import *
from myapp.views_panel_estadisticas import *
from myapp.views_nomina import *
from myapp.views_soporte import *
from myapp.views_dashboard import *
from myapp.views_soporte_admin import *
from myapp.views_instalacion_admin import *
from myapp.views_reportes_admin import * 
from myapp.views_inventario import *
def es_admin_o_superuser(user):
    return user.is_superuser or user.groups.filter(name='Administrador').exists()

urlpatterns = [
    #URLS DE INICIO
    path('', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
    
    # API para datos en tiempo real (AJAX)
    path('dashboard/datos-api/', dashboard_datos_api, name='dashboard_api'),
    #URLS DE ADMINISTRACION
    path('lista_usuarios/', lista_usuarios, name='lista_usuarios'),
    path('crear_usuario/', crear_usuario, name='crear_usuario'),
    path('usuario/<int:user_id>/editar',editar_usuario,name='editar_usuario'),
    path('mapa-usuarios/',mapa_usuarios, name='mapa_usuarios'),
    path('api/ubicaciones/', api_ubicaciones, name='api_ubicaciones'),
    path('panel-admin/', panel_administrativo, name='panel_administrativo'),
    path('administrador/contratos/', gestionar_contratos, name='gestionar_contratos'),
    path('contrato/<int:contrato_id>/completar/', completar_contrato, name='completar_contrato'),
    path('contrato/<int:contrato_id>/editar/', editar_contrato, name='editar_contrato'),
    path('listar/cuadrilla/',lista_cuadrillas, name='lista_cuadrillas'),
    path('crear/cuadrilla/',crear_cuadrilla, name='crear_cuadrilla'),
    path('<int:pk>/editar/', editar_cuadrilla, name='editar_cuadrilla'),
    path('cuadrillas/api/<int:pk>/',api_detalle_cuadrilla, name='api_detalle_cuadrilla'),
    path('cuadrillas/<int:pk>/cambiar-estado/', cambiar_estado_cuadrilla, name='cambiar_estado_cuadrilla'),
    path('cuadrillas/<int:pk>/eliminar/',eliminar_cuadrilla, name='eliminar_cuadrilla'),
    path('asignaciones/', lista_asignaciones, name='lista_asignaciones'),
    path('asignaciones/asignar/<int:item_id>/', asignar_contrato, name='asignar_contrato'),
    path('asignaciones/desasignar/<int:asignacion_id>/', desasignar_contrato, name='desasignar_contrato'),
    path('panel-estadisticas/', panel_estadisticas, name='panel_estadisticas'),
    path('usuarios/<int:user_id>/cambiar-estado/', cambiar_estado_usuario, name='cambiar_estado_usuario'),
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
    path('contrato/<int:contrato_id>/no-completado/', marcar_contrato_no_completado, name='marcar_contrato_no_completado'),
    path('contrato/crear/error/', crear_contrato_error, name='crear_contrato_error'),
    path('capturar-ubicacion-vendedor/', capturar_ubicacion_vendedor, name='capturar_ubicacion_vendedor'),
    path('cuadrillas/estado/', estado_cuadrillas, name='estado_cuadrillas'),
    path('reporte/', reporte_vendedor, name='reporte_vendedor'),
    path('api/reporte-datos/', api_reporte_datos, name='api_reporte_datos'),
    path('contrato/<int:contrato_id>/completar-pago/', completar_pago, name='completar_pago'),
    #URLS DE INSTALADORES
     path('instalaciones/', instalaciones_pendientes, name='instalaciones_pendientes'),
    path('instalaciones/<int:instalacion_id>/realizar/', realizar_instalacion, name='realizar_instalacion'),
    path('capturar-ubicacion-instalador/', capturar_ubicacion_instalador, name='capturar_ubicacion_instalador'),
    path('instalacion/detalle/<int:instalacion_id>/', obtener_detalle_instalacion, name='detalle_instalacion'),
    path('reporte-instalador/', reporte_instalador, name='reporte_instalador'),
    #URLS DE VENTA DIRECTA
    path('ventas-directas/',lista_ventas_directas, name='lista_ventas_directas'),
    path('ventas-directas/crear/',crear_venta_directa, name='crear_venta_directa'),
    path('ventas-directas/<int:venta_id>/editar/',editar_venta_directa, name='editar_venta_directa'),
    
    path('ventas-directas/<int:venta_id>/detalle/', detalle_venta_directa, name='detalle_venta_directa'),
    path('ventas-directas/<int:venta_id>/cambiar-estado/', cambiar_estado_venta, name='cambiar_estado_venta'),
    #URLS NOMINA
    path('nomina/', resumen_nomina, name='resumen_nomina'),
    path('nomina/vendedor/<int:vendedor_id>/', detalle_nomina_vendedor, name='detalle_nomina_vendedor'),
    path('nomina/recalcular/', recalcular_nomina, name='recalcular_nomina'),
    #Soporte
    path('soportes/', lista_soportes, name='lista_soportes'),
    path('soporte/nuevo/', crear_soporte_unificado, name='crear_soporte_unificado'),
    path('soporte/<int:soporte_id>/editar/', editar_soporte, name='editar_soporte'),
    path('soporte/<int:soporte_id>/detalle-json/', detalle_soporte_json, name='detalle_soporte_json'),
    #Soporte Admin
    path('soporte/<int:soporte_id>/editar/', editar_soporte, name='editar_soporte'),
    
    # API: Obtener detalles de soporte en JSON (para el modal)
    path('soporte/<int:soporte_id>/detalle-json/', detalle_soporte_admin, name='detalle_soporte_json'),
    path('soportes/admin', lista_soportes_admin, name='lista_soportes_admin'),
    # API: Cambiar estado del soporte
    path('soporte/<int:soporte_id>/cambiar-estado/', cambiar_estado_admin, name='cambiar_estado_soporte'),
    path('instalacion/<int:instalacion_id>/historial-soportes/', historial_soportes_instalacion, name='historial_soportes_instalacion'),
    path('soporte/<int:soporte_id>/detalle-modal/', detalle_soporte_modal, name='detalle_soporte_modal'),
    path('instalacion-por-contrato/<int:contrato_id>/', instalacion_por_contrato, name='instalacion_por_contrato'),
    
    #URLS ADMIN INSTALACION
    path('instalaciones/listar/', lista_instalaciones_admin, name='lista_instalaciones'),
    path('instalacion/<int:instalacion_id>/detalle-json/', detalle_instalacion_json, name='detalle_instalacion_json'),
    path('instalacion/<int:instalacion_id>/editar/', editar_instalacion, name='editar_instalacion'),
     # Reportes
    # URLs de Reportes
    path('reportes/', reportes_view, name='reportes'),
    path('api/reporte-ventas/', reporte_ventas_json, name='reporte_ventas_json'),
    path('api/reporte-instalaciones/', reporte_instalaciones_json, name='reporte_instalaciones_json'),
    path('api/reporte-soportes/', reporte_soportes_json, name='reporte_soportes_json'),
    path('api/reporte-inventario/', reporte_inventario_json, name='reporte_inventario_json'),
    path('exportar-reporte/', exportar_reporte, name='exportar_reporte'),
    #URLS DE INVENTARIO
    # URLs de Inventario
    path('inventario/', inventario_global_lista, name='inventario_global_lista'),
    path('inventario/agregar/', inventario_global_agregar, name='inventario_global_agregar'),
    path('inventario/ajustar/<int:material_id>/', inventario_global_ajustar, name='inventario_global_ajustar'),
    path('inventario/movimientos/', inventario_movimientos, name='inventario_movimientos'),
    # URLs de Inventario - Asignación a cuadrillas
    path('inventario/asignar-cuadrilla/', inventario_asignar_cuadrilla, name='inventario_asignar_cuadrilla'),
    path('inventario/cuadrilla/<int:cuadrilla_id>/', inventario_cuadrilla_detalle, name='inventario_cuadrilla_detalle'),
    path('inventario/devolver/<int:inventario_id>/', inventario_devolver_cuadrilla, name='inventario_devolver_cuadrilla'),
    path('inventario/todas-cuadrillas/', inventario_todas_cuadrillas, name='inventario_todas_cuadrillas'),
    path('inventario/panel/', panel_inventario, name='panel_inventario'),
    path('inventario/movimientos-cuadrilla/<int:cuadrilla_id>/', inventario_movimientos_cuadrilla, name='inventario_movimientos_cuadrilla'),
    path('mi-inventario/', mi_inventario, name='mi_inventario'),

]


