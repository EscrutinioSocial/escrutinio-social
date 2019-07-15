from django.conf import settings
from datetime import timedelta
from django.db.models.signals import post_save
from adjuntos.models import *

@receiver(post_save, sender=Identificacion)
def save_identificacion(sender, instance=None, created=False, update_fields=None, **kwargs):
    if not instance.attachment:
        return

    # Si se cambió el campo consolidada, no tengo que volver a entrar.
    if update_fields and 'consolidada' in update_fields:
        return

    # Me quedo con todas las identificaciones para ese attachment.
    # Formato: (mesa_id, status, cantidad)
    # Ejemplo:
    #  [
    #       (0, 'spam', 2),
    #       (0, 'invalida', 1),
    #       (1, 'identificada', 1),
    #       (2, 'identificada', 1),
    #  ]
    status_count_dict = instance.attachment.status_count()

    mesa_id_consolidada = None
    for (mesa_id, status, cantidad, cuantos_csv) in status_count_dict:
        if status == Identificacion.STATUS.identificada \
            and (cantidad >= settings.MIN_COINCIDENCIAS_IDENTIFICACION
                or cuantos_csv > 0):
            mesa_id_consolidada = mesa_id
            break

    if mesa_id_consolidada:
        # Consolidamos una mesa, ya sea por CSV o por multicoincidencia.

        identificaciones_correctas = instance.attachment.identificaciones.filter(mesa_id=mesa_id_consolidada, status=Identificacion.STATUS.identificada)

        identificacion_con_csv = identificaciones_correctas.filter(source=Identificacion.SOURCES.csv).first()

        # Si hay una de CSV, es la consolidada. Si no, cualquiera del resto.
        consolidada = identificacion_con_csv if identificacion_con_csv else identificaciones_correctas.first()

        # Ésta tiene que quedar como consolidada.
        consolidada.set_consolidada()

        consolidada_set = [consolidada.id]
        # Identifico el attachment.
        status_attachment = consolidada.status
        mesa_attachment = consolidada.mesa

        # TODO - para reportar trolls
        # sumar 200 a scoring de los usuarios que identificaron el acta diferente
    else:
        status_attachment = Attachment.STATUS.sin_identificar
        mesa_attachment = None
        consolidada_set = []

    # Identifico el attachment.
    instance.attachment.status = status_attachment
    instance.attachment.mesa = mesa_attachment
    instance.attachment.save(update_fields=['mesa', 'status'])
        
    # El resto no tiene que quedar como consolidada.
    instance.attachment.identificaciones.exclude(id__in=consolidada_set).update(consolidada=False)
