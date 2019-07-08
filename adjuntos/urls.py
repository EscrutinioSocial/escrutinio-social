from django.conf.urls import url
from .views import elegir_adjunto, IdentificacionCreateView, editar_foto, AgregarAdjuntos

urlpatterns = [
    url(r'^$', elegir_adjunto, name="elegir-adjunto"),
    url(r'^(?P<attachment_id>\d+)/$', IdentificacionCreateView.as_view(), name='asignar-mesa'),
    url(r'^(?P<attachment_id>\d+)/editar-foto$', editar_foto, name='editar-foto'),
    url(r'^agregar$', AgregarAdjuntos.as_view(), name="agregar-adjuntos"),
]
