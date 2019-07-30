from elecciones.models import Mesa, Categoria
from adjuntos.models import Attachment


def contadores(request):
    return {
        'mesas_pendientes_count': Mesa.con_carga_pendiente().count() + Attachment.sin_identificar(request.user.fiscal).count(),

    }


def categoria_default(request):
    e = Categoria.objects.filter(sensible=False).first()
    if e is None:
        raise EnvironmentError("Debe exisitr una categoría no sensible")
    return {
        'primera_categoria': e.id
    }

