from django.conf.urls import url
from . import views

urlpatterns = [
    url('^reportar-problema/(?P<mesa_numero>\d+)$',
        views.ProblemaCreate.as_view(), name='reportar-problema'),
    url(r'^cambiar_estado_problema/(?P<problema_id>\d+)/(?P<nuevo_estado>[\w-]+)$',
        views.cambiar_estado_problema, name='cambiar-estado-problema'),
]
