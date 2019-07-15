from django.conf import settings
from datetime import timedelta
from adjuntos.models import *
from django.db import transaction

def consolidar_identificaciones(attachment):
    """
    Consolida todas las identificaciones del Attachment parámetro.
    Deja sólo una como consolidada, si están dadas las condiciones.
    Si hay una identificación con origen csv, ésa es la consolidada.

    En cualquier caso adecúa el estado de identificación del attach parámetro
    y lo asocia a la mesa identificada o a ninguna, si no quedó identificado.
    """

    # Primero me quedo con todas las identificaciones para ese attachment.
    # Formato: (mesa_id, status, cantidad)
    # Ejemplo:
    #  [
    #       (0, 'spam', 2),
    #       (0, 'invalida', 1),
    #       (1, 'identificada', 1),
    #       (2, 'identificada', 1),
    #  ]
    status_count_dict = attachment.status_count()

    mesa_id_consolidada = None
    for (mesa_id, status, cantidad, cuantos_csv) in status_count_dict:
        if status == Identificacion.STATUS.identificada \
            and (cantidad >= settings.MIN_COINCIDENCIAS_IDENTIFICACION
                or cuantos_csv > 0):
            mesa_id_consolidada = mesa_id
            break

    if mesa_id_consolidada:
        # Consolidamos una mesa, ya sea por CSV o por multicoincidencia.

        identificaciones_correctas = attachment.identificaciones.filter(mesa_id=mesa_id_consolidada, status=Identificacion.STATUS.identificada)

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
    # Notar que esta identificación podría estar sumando al attachment a una mesa que ya tenga.
    # Eso es correcto.
    # También podría estar haciendo pasar una attachment identificado al estado sin_identificar,
    # porque ya no está más vigente alguna identificación que antes sí.
    attachment.status = status_attachment
    attachment.mesa = mesa_attachment
    attachment.save(update_fields=['mesa', 'status'])

    # El resto no tiene que quedar como consolidada.
    attachment.identificaciones.exclude(id__in=consolidada_set).update(consolidada=False)

@transaction.atomic
def consumir_novedades_identificacion():
    novedades = NovedadesIdentificacion.objects.select_for_update(
                        skip_locked=True
                    ).all()

    # Agrupo por attach.
    # Ahora bien, no puedo hacerlo directo sobre el query que las seleccionó 'FOR UPDATE',
    # así que las selecciono de nuevo.
    attachments_con_novedades = Attachment.objects.filter(id__in=novedades.values('identificacion__attachment'))
    for attachment in attachments_con_novedades:
        consolidar_identificaciones(attachment)

    # Todas consumidas, las borro.
    novedades.delete()