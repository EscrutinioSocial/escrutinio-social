from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^(?P<attachment_id>\d+)/$', views.IdentificacionCreateView.as_view(), name='asignar-mesa'),
    url(r'^(?P<attachment_id>\d+)/problema$', views.IdentificacionProblemaCreateView.as_view(), name='asignar-problema'),
    url(r'^(?P<attachment_id>\d+)/editar-foto$', views.editar_foto, name='editar-foto'),
    url(r'^agregar$', views.AgregarAdjuntos.as_view(), name="agregar-adjuntos"),
    url(r'^agregar-adjuntos-csv/$', views.AgregarAdjuntosImportados.as_view(), name="agregar-adjuntos-csv"),
]
