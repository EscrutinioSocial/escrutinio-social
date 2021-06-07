from django.urls import re_path
from . import views

urlpatterns = [
    re_path(
        r"^reportar-problema/(?P<mesa_numero>\d+)$",
        views.ProblemaCreate.as_view(),
        name="reportar-problema",
    ),
    re_path(
        r"^cambiar_estado_problema/(?P<problema_id>\d+)/(?P<nuevo_estado>[\w-]+)$",
        views.cambiar_estado_problema,
        name="cambiar-estado-problema",
    ),
]
