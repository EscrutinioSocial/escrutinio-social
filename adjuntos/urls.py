from django.conf.urls import url
from .views import AsignarMesaAdjunto, editar_foto, AgregarAdjuntos, post_asignar_mesa

urlpatterns = [
    url(r'^(?P<attachment_id>\d+)/$', AsignarMesaAdjunto.as_view(), name='asignar-mesa'),
    url(r'^(?P<attachment_id>\d+)/editar-foto$', editar_foto, name='editar-foto'),
    url(r'^agregar$', AgregarAdjuntos.as_view(), name="agregar-adjuntos"),
    url(r'^post-asignar-mesa/(?P<decision>\w+)/(?P<contenido>\w+)$', post_asignar_mesa, name="post-asignar-mesa"),
]
