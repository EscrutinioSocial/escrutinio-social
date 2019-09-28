from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^cambiar_status_troll/(?P<fiscal_id>\d+)/(?P<prender>[\w-]+)$',
        views.cambiar_status_troll, name='cambiar-status-troll'),
    url('monitor_antitrolling',
        views.MonitorAntitrolling.as_view(), name='monitoreo-antitrolling'),
    url(r'^monitor_antitrolling/(?P<mensaje>[\w-]+)$',
        views.monitor_antitrolling_con_mensaje, name='monitoreo-antitrolling-con-mensaje'),
    url('limpiar_marcas_troll',
        views.limpiar_marcas_troll, name='limpiar-marcas-troll'),
]
