from django.urls import re_path
from . import views

urlpatterns = [
    re_path(
        r"^cambiar_status_troll/(?P<fiscal_id>\d+)/(?P<prender>[\w-]+)$",
        views.cambiar_status_troll,
        name="cambiar-status-troll",
    ),
    re_path(
        r"monitor_antitrolling",
        views.MonitorAntitrolling.as_view(),
        name="monitoreo-antitrolling",
    ),
    re_path(
        r"limpiar_marcas_troll", views.limpiar_marcas_troll, name="limpiar-marcas-troll"
    ),
]
