from django.conf import settings
from django.db import models
from model_utils.models import TimeStampedModel
from model_utils import Choices
from model_utils.fields import StatusField

from elecciones.models import MesaCategoria
from adjuntos.models import Attachment


class EventoScoringTroll(TimeStampedModel):
    """
    Representa un evento que afecta el scoring troll de un fiscal; puede aumentarlo o disminuirlo.
    Algunos se generan automáticamente, como efecto colateral de algunas acciones
    que lleva a cabo la aplicación, p.ej. cambio de estado de una MesaCategoria.
    Otros resultan de una acción que toma deliberadamente un usuario, p.ej. quitarle el status de troll a un fiscal.
    """

    MOTIVO = Choices(
        ('carga_valores_distintos_a_confirmados', 'Carga valores distintos a los confirmados'),
        ('identificacion_attachment_distinta_a_confirmada', 'Identifica un attachment de una forma distinta a la confirmada'),
        ('remocion_marca_troll', 'Se remueve la marca de troll a un fiscal'),
    )
    "descripcion del motivo para cambiar el scoring troll de un fiscal"
    motivo = StatusField(choices_name='MOTIVO')

    "referencia a la MesaCategoria para eventos por carga de valores distintos a los confirmados; None para los otros eventos"
    mesa_categoria = models.ForeignKey(MesaCategoria, null=True, on_delete=models.CASCADE)

    "referencia al Attachment para eventos por identificación distinta a la confirmada; None para los otros eventos"
    attachment = models.ForeignKey(Attachment, null=True, on_delete=models.CASCADE)

    "True si el evento se genera automáticamente, False si es resultado de una decisión de un usuario"
    automatico = models.BooleanField(default=True)

    "referencia al usuario que tomó la decisión de cambiar un scoring troll para eventos manuales; None para eventos automaticos"
    actor = models.ForeignKey('fiscales.Fiscal', null=True, on_delete=models.SET_NULL)

    "referencia al data entry cuyo scoring troll cambia como consecuencia de este evento"
    fiscal_afectado = models.ForeignKey('fiscales.Fiscal', null=False, related_name='eventos_scoring_troll', on_delete=models.CASCADE)

    "cuánto varía el scoring troll del fiscal afectado."
    "Valores positivos para aumento de scoring, valores positivos para disminución"
    variacion = models.IntegerField(null=False, default=0)



class CambioEstadoTroll(TimeStampedModel):
    """
    Representa la decisión de cambiar el status de troll de un fiscal.
    Algunos son automáticos, ocurren cuando el scoring troll de un fiscal supera el mínimo indicado en los settings.
    Otros son manuales, ocurren cuando un usuario experto decide que un fiscal es troll, o que no es troll,
    independientemente del scoring acumulado por el mismo.
    """
    
    "True si el evento se genera automáticamente, False si es resultado de una decisión de un usuario"
    automatico = models.BooleanField(default=True)

    "referencia al usuario que tomó la decisión de cambiar el status de troll de un fiscal;" 
    "None si el cambio de status se dispara en forma automática"
    actor = models.ForeignKey('fiscales.Fiscal', null=True, on_delete=models.SET_NULL)

    "referencia al evento por el cual un fiscal cambia su status de troll"
    evento_disparador = models.ForeignKey(EventoScoringTroll, null=False, on_delete=models.CASCADE)

    "referencia al fiscal que cambia su status de troll"
    fiscal_afectado = models.ForeignKey('fiscales.Fiscal', null=False, related_name='cambios_estado_troll', on_delete=models.CASCADE)

    "True si el fiscal afectado pasa a ser considerado troll, False si deja de ser considerado troll"
    troll = models.BooleanField(default=True)



## Funciones para manejo de scoring troll

def aumentar_scoring_troll_identificacion(variacion, identificacion):
    """
    Aumenta el scoring troll de un fiscal por motivos relacionados con una identificacion. Si corresponde, marcar al fiscal como troll.
    """

    fiscal = identificacion.fiscal
    scoring_anterior = fiscal.scoring_troll()
    nuevo_evento = EventoScoringTroll.objects.create(
        motivo=EventoScoringTroll.MOTIVO.identificacion_attachment_distinta_a_confirmada,
        attachment=identificacion.attachment,
        automatico=True,
        fiscal_afectado=fiscal,
        variacion=variacion
    )
    scoring_actualizado = scoring_anterior + variacion
    if (scoring_actualizado >= settings.SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL):
        marcar_fiscal_troll(fiscal, nuevo_evento)



def marcar_fiscal_troll(fiscal, evento_disparador):
    """
    Se marca a un fiscal como troll
    """

    CambioEstadoTroll.objects.create(
        automatico=True,
        evento_disparador=evento_disparador,
        fiscal_afectado=fiscal,
        troll=True
    )
    fiscal.marcar_como_troll()
