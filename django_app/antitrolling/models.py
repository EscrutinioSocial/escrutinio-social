from constance import config
from django.conf import settings
from django.db import models
from model_utils.models import TimeStampedModel
from model_utils import Choices
from model_utils.fields import StatusField

from elecciones.models import MesaCategoria, Mesa
from adjuntos.models import Attachment

class EventoScoringTroll(TimeStampedModel):
    """
    Representa un evento que afecta el scoring troll de un fiscal; puede aumentarlo o disminuirlo.
    Algunos se generan automáticamente, como efecto colateral de algunas acciones
    que lleva a cabo la aplicación, p.ej. cambio de estado de una MesaCategoria.
    Otros resultan de una acción que toma deliberadamente un usuario, p.ej. quitarle el status de troll a un fiscal.
    """

    MOTIVOS = Choices(
        ('carga_valores_distintos_a_confirmados', 'Carga valores distintos a los confirmados'),
        ('indica_problema_mesa_categoria_confirmada', 'Indica "problema" para una mesa/categoría con carga confirmada'),
        ('identificacion_attachment_distinta_a_confirmada', 'Identifica un attachment de una forma distinta a la confirmada'),
        ('problema_descartado', 'Se descarta un "problema" reportado por el usuario.'),
        ('marca_explicita_troll', 'Un usuario marca explitimamente a un fiscal como troll'),
        ('remocion_marca_troll', 'Se remueve la marca de troll a un fiscal'),
        ('carga_aceptada', 'Carga los valores aceptados'),
        ('identificacion_aceptada', 'Realiza una identificación con la decisión aceptada'),
    )
    # descripción del motivo para cambiar el scoring troll de un fiscal
    motivo = models.CharField(max_length=50, choices=MOTIVOS)

    # Referencia a la Mesa para eventos de descarte de problemas;
    # None para los otros eventos
    mesa = models.ForeignKey(Mesa, null=True, blank=True, on_delete=models.CASCADE)

    # Referencia a la MesaCategoria para eventos por carga de valores distintos a los confirmados;
    # None para los otros eventos
    mesa_categoria = models.ForeignKey(MesaCategoria, null=True, blank=True, on_delete=models.CASCADE)

    # Referencia al Attachment para eventos por identificación distinta a la confirmada;
    # None para los otros eventos
    attachment = models.ForeignKey(Attachment, null=True, blank=True, on_delete=models.CASCADE)

    # True si el evento se genera automáticamente,
    # False si es resultado de una decisión de un usuario
    automatico = models.BooleanField(default=True)

    # referencia al usuario que tomó la decisión de cambiar un scoring troll para eventos manuales;
    # None para eventos automaticos
    actor = models.ForeignKey('fiscales.Fiscal', null=True, on_delete=models.SET_NULL)

    # referencia al data entry cuyo scoring troll cambia como consecuencia de este evento
    fiscal_afectado = models.ForeignKey('fiscales.Fiscal', null=False, related_name='eventos_scoring_troll', on_delete=models.CASCADE)

    # cuánto varía el scoring troll del fiscal afectado.
    # Valores positivos para aumento de scoring, valores positivos para disminución
    variacion = models.IntegerField(null=False, default=0)


class CambioEstadoTroll(TimeStampedModel):
    """
    Representa la decisión de cambiar el status de troll de un fiscal.
    Algunos son automáticos, ocurren cuando el scoring troll de un fiscal
    supera el mínimo indicado en los settings.

    Otros son manuales, ocurren cuando un usuario experto decide que un fiscal es troll,
    o que no es troll, independientemente del scoring acumulado por el mismo.
    """

    # True si el evento se genera automáticamente, False si es resultado de una decisión de un usuario
    automatico = models.BooleanField(default=True)

    # Referencia al usuario que tomó la decisión de cambiar el status de troll de un fiscal;
    # None si el cambio de status se dispara en forma automática
    actor = models.ForeignKey('fiscales.Fiscal', null=True, on_delete=models.SET_NULL)

    # Referencia al evento por el cual un fiscal cambia su status de troll
    evento_disparador = models.ForeignKey(EventoScoringTroll, null=False, on_delete=models.CASCADE)

    # Referencia al fiscal que cambia su status de troll
    fiscal_afectado = models.ForeignKey(
        'fiscales.Fiscal', null=False, related_name='cambios_estado_troll', on_delete=models.CASCADE
    )

    # True si el fiscal afectado pasa a ser considerado troll, False si deja de ser considerado troll"
    troll = models.BooleanField(default=True)


# Funciones internas

def registrar_cambio_scoring_troll(fiscal, variacion, evento):
    era_troll = fiscal.troll
    fiscal.cambiar_scoring_troll(variacion)
    if not era_troll and fiscal.scoring_troll() >= config.SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL:
        marcar_fiscal_troll(fiscal, evento)



# Funciones para manejar el status de troll de un fiscal

def marcar_explicitamente_fiscal_troll(fiscal, actor):
    evento = crear_evento_marca_explicita_como_troll(fiscal, actor)
    marcar_fiscal_troll(fiscal, evento)


def marcar_fiscal_troll(fiscal, evento_disparador):
    """
    Se marca a un fiscal como troll
    """
    CambioEstadoTroll.objects.create(
        automatico=evento_disparador.automatico,
        evento_disparador=evento_disparador,
        actor=evento_disparador.actor,
        fiscal_afectado=fiscal,
        troll=True
    )
    aplicar_marca_troll(fiscal)


def aplicar_marca_troll(fiscal):
    """
    Se marca al fiscal indicado como troll, y se ejecutan las consecuencias de dicha decisión.
    """
    from antitrolling.efecto import efecto_determinacion_fiscal_troll

    fiscal.troll = True
    fiscal.save(update_fields=['troll'])
    efecto_determinacion_fiscal_troll(fiscal)


def marcar_explicitamente_fiscal_no_troll(fiscal, actor, nuevo_scoring):
    """
    Un UE decidió, explícitamente, quitarle a un fiscal la marca de troll.
    """
    variacion = nuevo_scoring - fiscal.scoring_troll()
    evento = crear_evento_quitar_explicitamente_marca_troll(fiscal, actor, variacion)
    fiscal.cambiar_scoring_troll(variacion)
    marcar_fiscal_no_troll(fiscal, evento)


def marcar_fiscal_no_troll(fiscal, evento_disparador):
    """
    Se marca a un fiscal como no troll
    """
    CambioEstadoTroll.objects.create(
        automatico=evento_disparador.automatico,
        evento_disparador=evento_disparador,
        actor=evento_disparador.actor,
        fiscal_afectado=fiscal,
        troll=False
    )
    quitar_marca_troll(fiscal)


def quitar_marca_troll(fiscal):
    """
    Se quita la marca de troll al fiscal indicado. Esta decisión no tiene consecuencias.
    """
    fiscal.troll = False
    fiscal.save(update_fields=['troll'])


# Funciones para manejo de scoring troll

def aumentar_scoring_troll_identificacion(variacion, identificacion):
    """
    Aumenta el scoring troll de un fiscal por motivos relacionados con una identificacion.
    Si corresponde, marcar al fiscal como troll.
    """
    afectar_scoring_troll_evento_automatico(
        identificacion.fiscal, EventoScoringTroll.MOTIVOS.identificacion_attachment_distinta_a_confirmada,
        identificacion.attachment, None, variacion)


def disminuir_scoring_troll_identificacion(variacion, identificacion):
    """
    Disminuye el scoring de un fiscal que identificó un attachment tomando la decisión aceptada.
    """
    afectar_scoring_troll_evento_automatico(
        identificacion.fiscal, EventoScoringTroll.MOTIVOS.identificacion_aceptada,
        identificacion.attachment, None, variacion * -1)


def aumentar_scoring_troll_carga(variacion, carga, motivo):
    """
    Aumenta el scoring troll de un fiscal por motivos relacionados con una carga.
    Si corresponde, marcar al fiscal como troll.
    """
    afectar_scoring_troll_evento_automatico(
        carga.fiscal, motivo, None, carga.mesa_categoria, variacion)


def disminuir_scoring_troll_carga(variacion, carga):
    """
    Disminuye el scoring de un fiscal que realizó una carga con los valores aceptados.
    """
    afectar_scoring_troll_evento_automatico(
        carga.fiscal, EventoScoringTroll.MOTIVOS.carga_aceptada, 
        None, carga.mesa_categoria, variacion * -1)


def afectar_scoring_troll_evento_automatico(fiscal, motivo, attachment, mesacat, variacion):
    nuevo_evento = EventoScoringTroll.objects.create(
        motivo=motivo,
        attachment=attachment,
        mesa_categoria=mesacat,
        automatico=True,
        fiscal_afectado=fiscal,
        variacion=variacion
    )
    registrar_cambio_scoring_troll(fiscal, variacion, nuevo_evento)


def aumentar_scoring_troll_problema_descartado(variacion, fiscal_afectado, mesa, attachment):
    nuevo_evento = EventoScoringTroll.objects.create(
        motivo=EventoScoringTroll.MOTIVOS.problema_descartado,
        attachment=attachment,
        mesa=mesa,
        automatico=False,
        fiscal_afectado=fiscal_afectado,
        variacion=variacion
    )
    registrar_cambio_scoring_troll(fiscal_afectado, variacion, nuevo_evento)


def crear_evento_marca_explicita_como_troll(fiscal, actor):
    """
    Se crea, registra y devuelve un EventoScoringTroll que indica que un usuario (el 'actor')
    indica explícitamente que un fiscal debe ser considerado troll
    """

    nuevo_evento = EventoScoringTroll.objects.create(
        motivo=EventoScoringTroll.MOTIVOS.marca_explicita_troll,
        automatico=False,
        actor=actor,
        fiscal_afectado=fiscal,
        variacion=0
    )
    return nuevo_evento


def crear_evento_quitar_explicitamente_marca_troll(fiscal, actor, variacion):
    """
    Se crea, registra y devuelve un EventoScoringTroll que indica que un usuario (el 'actor')
    indica explícitamente que un fiscal ya no debe ser considerado troll
    """
    nuevo_evento = EventoScoringTroll.objects.create(
        motivo=EventoScoringTroll.MOTIVOS.remocion_marca_troll,
        automatico=False,
        actor=actor,
        fiscal_afectado=fiscal,
        variacion=variacion
    )
    return nuevo_evento





