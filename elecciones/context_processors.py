from elecciones.models import Mesa
from adjuntos.models import Attachment


def contadores(request):
    return {
        'adjuntos_count': Attachment.sin_asignar().count(),
        'mesas_pendientes_count': Mesa.con_carga_pendiente().count(),
        'mesas_a_confirmar_count': Mesa.con_carga_a_confirmar().count()
    }
