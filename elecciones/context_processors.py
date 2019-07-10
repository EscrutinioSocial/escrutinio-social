from elecciones.models import Mesa, Categoria
from adjuntos.models import Attachment


def contadores(request):
    e = Categoria.objects.first()
    return {
        'mesas_pendientes_count': Mesa.con_carga_pendiente().count() + Attachment.sin_asignar().count() + Mesa.con_carga_a_confirmar().count(),

        'primera_categoria': e.id if e is not None else 1   # las urls esperan un entero.
                                                           # aunque no exista el objeto
    }


