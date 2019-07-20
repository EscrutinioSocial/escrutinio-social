from django.conf import settings
from adjuntos.models import Identificacion

from .models import aumentar_scoring_troll_identificacion


def efecto_scoring_troll_asociacion_attachment(attachment, mesa):
    """
    Realizar las actualizaciones de scoring troll que correspondan
    a partir de que se confirma la asignacion de mesa a un attachment 
    """

    ## para cada identificacion del attachment que no coincida en mesa, aumentar el scoring troll del fiscal que la hizo
    for identificacion in attachment.identificaciones.filter(invalidada=False):
        if ((identificacion.status != Identificacion.STATUS.identificada) or (identificacion.mesa != mesa)):
            aumentar_scoring_troll_identificacion(
                settings.SCORING_TROLL_IDENTIFICACION_DISTINTA_A_CONFIRMADA, identificacion
            )



def diferencia_opciones(carga_1, carga_2):
    votos_carga_1 = list(carga_1.reportados.order_by("opcion__orden").all())
    votos_carga_2 = list(carga_2.reportados.order_by("opcion__orden").all())
    diferencia = 0

    # se calcula la diferencia para cada voto en la carga 1
    for voto_1 in votos_carga_1:
        cantidad_votos_1 = voto_1.votos
        voto_misma_opcion_2 = next((voto_2 for voto_2 in votos_carga_2 if voto_2.opcion == voto_1.opcion), None)
        if (voto_misma_opcion_2):
            cantidad_votos_2 = voto_misma_opcion_2.votos 
            diferencia += abs(cantidad_votos_1 - cantidad_votos_2)
            votos_carga_2.remove(voto_misma_opcion_2)
        else:
            diferencia += cantidad_votos_1
    
    # los votos que quedaron en votos_carga_2 no tienen correspondencia en votos_carga_1
    for voto_2 in votos_carga_2:
        diferencia += voto_2.votos
    
    return diferencia
