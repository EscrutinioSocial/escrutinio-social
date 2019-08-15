from django.conf import settings
import structlog
from adjuntos.models import Attachment, Identificacion
from elecciones.models import Carga, MesaCategoria
from fiscales.models import Fiscal
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.db.models import Count
from django.dispatch import receiver
from django.db.models.signals import post_save
from problemas.models import Problema
from antitrolling.efecto import (
    efecto_scoring_troll_asociacion_attachment, efecto_scoring_troll_confirmacion_carga
)


logger = structlog.get_logger(__name__)


def consolidar_cargas_por_tipo(cargas, tipo):
    """
    El parámetro cargas tiene solamente cargas del tipo parámetro.
    """
    statuses = {
        Carga.TIPOS.total: {
            'consolidada_dc': MesaCategoria.STATUS.total_consolidada_dc,
            'consolidada_csv': MesaCategoria.STATUS.total_consolidada_csv,
            'en_conflicto': MesaCategoria.STATUS.total_en_conflicto,
            'sin_consolidar': MesaCategoria.STATUS.total_sin_consolidar,
        },
        Carga.TIPOS.parcial: {
            'consolidada_dc': MesaCategoria.STATUS.parcial_consolidada_dc,
            'consolidada_csv': MesaCategoria.STATUS.parcial_consolidada_csv,
            'en_conflicto': MesaCategoria.STATUS.parcial_en_conflicto,
            'sin_consolidar': MesaCategoria.STATUS.parcial_sin_consolidar,
        }
    }

    cargas_agrupadas_por_firma = cargas.values('firma').annotate(count=Count('firma')).order_by('-count')

    # Como están ordenadas por cantidad de coincidencia,
    # si alguna tiene doble carga, es la primera.
    primera = cargas_agrupadas_por_firma.first()

    if primera['count'] >= settings.MIN_COINCIDENCIAS_CARGAS:
        # Encontré doble carga coincidente.
        status_resultante = statuses[tipo]['consolidada_dc']
        # Me quedo con alguna de las que tiene doble carga coincidente.
        carga_testigo_resultante = cargas.filter(firma=primera['firma']).first()

    elif cargas_agrupadas_por_firma.count() > 1:
        # Alguna viene de CSV?
        cargas_csv = cargas.filter(origen=Carga.SOURCES.csv)
        if cargas_csv.count() > 0:
            status_resultante = statuses[tipo]['consolidada_csv']
            # Me quedo con alguna de las CSV como testigo.
            carga_testigo_resultante = cargas_csv.first()
        else:
            # No hay doble coincidencia ni carga de CSV, pero hay más de una firma. Caso de conflicto.
            status_resultante = statuses[tipo]['en_conflicto']
            # Ninguna.
            carga_testigo_resultante = None

    else:
        # Hay sólo una firma.
        # Viene de CSV?
        cargas_csv = cargas.filter(origen=Carga.SOURCES.csv)
        if cargas_csv.count() > 0:
            status_resultante = statuses[tipo]['consolidada_csv']
            # Me quedo con alguna de las CSV como testigo.
            carga_testigo_resultante = cargas_csv.first()
        else:
            # No viene de CSV.
            status_resultante = statuses[tipo]['sin_consolidar']
            # Me quedo con la única que hay.
            carga_testigo_resultante = cargas.filter(firma=primera['firma']).first()

    return status_resultante, carga_testigo_resultante


def consolidar_cargas_con_problemas(cargas_que_reportan_problemas):

    # Tomo como "muestra" alguna de las que tienen problemas.
    carga_con_problema = cargas_que_reportan_problemas.first()
    # Confirmo el problema porque varios reportaron problemas.
    Problema.confirmar_problema(carga=carga_con_problema)

    return MesaCategoria.STATUS.con_problemas, None


def consolidar_cargas(mesa_categoria):
    """
    Consolida todas las cargas de la MesaCategoria parámetro.
    """
    statuses_que_permiten_analizar_carga_total = [
        MesaCategoria.STATUS.sin_cargar,
        MesaCategoria.STATUS.parcial_consolidada_dc,
        MesaCategoria.STATUS.parcial_consolidada_csv
    ]
    statuses_que_requieren_computar_efecto_trolling = [
        MesaCategoria.STATUS.parcial_consolidada_dc,
        MesaCategoria.STATUS.total_consolidada_dc
    ]

    # Por lo pronto el status es sin_cargar.
    status_resultante = MesaCategoria.STATUS.sin_cargar
    carga_testigo_resultante = None

    # Obtengo todas las cargas actualmente válidas para mesa_categoria.
    cargas = mesa_categoria.cargas.filter(invalidada=False)

    # Si no hay cargas, no sigo.
    if cargas.count() == 0:
        mesa_categoria.actualizar_status(status_resultante, carga_testigo_resultante)
        return

    # Hay cargas.

    # Me fijo si es un problema.
    cargas_que_reportan_problemas = cargas.filter(tipo=Carga.TIPOS.problema)
    if cargas_que_reportan_problemas.count() >= settings.MIN_COINCIDENCIAS_CARGAS_PROBLEMA:
        status_resultante, carga_testigo_resultante = consolidar_cargas_con_problemas(
            cargas_que_reportan_problemas
        )
        mesa_categoria.actualizar_status(status_resultante, carga_testigo_resultante)
        return

    # A continuación voy probando los distintos status.

    # Primero les actualizo la firma.
    for carga in cargas:
        carga.actualizar_firma()

    # Analizo las parciales.
    cargas_parciales = cargas.filter(tipo=Carga.TIPOS.parcial)
    if cargas_parciales.exists():
        status_resultante, carga_testigo_resultante = consolidar_cargas_por_tipo(
            cargas_parciales, Carga.TIPOS.parcial
        )

    if status_resultante in statuses_que_permiten_analizar_carga_total:
        # Analizo las totales solo si no hay ninguna parcial, o si están consolidadas las parciales.
        # En otro caso no tiene sentido porque puedo encontrar cargas totales "residuales", pero
        # todavía no se resolvió la parcial.
        cargas_totales = cargas.filter(tipo=Carga.TIPOS.total)
        if cargas_totales.exists():
            status_resultante, carga_testigo_resultante = consolidar_cargas_por_tipo(
                cargas_totales, Carga.TIPOS.total
            )

    mesa_categoria.actualizar_status(status_resultante, carga_testigo_resultante)
    if status_resultante in statuses_que_requieren_computar_efecto_trolling:
        efecto_scoring_troll_confirmacion_carga(mesa_categoria)


def consolidar_identificaciones(attachment):
    """
    Consolida todas las identificaciones del Attachment parámetro.
    Deja una como testigo, si están dadas las condiciones.
    Si hay una identificación con origen csv, ésa es la testigo.

    En cualquier caso adecúa el estado de identificación del attach parámetro
    y lo asocia a la mesa identificada o a ninguna, si no quedó identificado.
    """

    # Primero me quedo con todas las identificaciones para ese attachment
    # que correspondan con una identificación y no con un problema.
    status_count = attachment.status_count(Identificacion.STATUS.identificada)

    mesa_id_consolidada = None
    for mesa_id, cantidad, cuantos_csv in status_count:
        if (cantidad >= settings.MIN_COINCIDENCIAS_IDENTIFICACION or cuantos_csv > 0):
            mesa_id_consolidada = mesa_id
            break

    if mesa_id_consolidada:
        # Consolidamos una mesa, ya sea por CSV o por coincidencia múltiple.

        identificaciones_correctas = attachment.identificaciones.filter(
            mesa_id=mesa_id_consolidada, status=Identificacion.STATUS.identificada
        )

        identificacion_con_csv = identificaciones_correctas.filter(source=Identificacion.SOURCES.csv).first()

        # Si hay una de CSV, es la testigo. Si no, cualquiera del resto.
        testigo = identificacion_con_csv if identificacion_con_csv else identificaciones_correctas.first()

        # Identifico el attachment.
        status_attachment = testigo.status
        mesa_attachment = testigo.mesa

        # Si tenía asociado un problema de "falta hoja", se soluciona automáticamente
        # porque se agregó un attachment.
        Problema.resolver_problema_falta_hoja(mesa_attachment)

        # aumentar el scoring de los usuarios que identificaron el acta diferente
        efecto_scoring_troll_asociacion_attachment(attachment, mesa_attachment)

    else:
        status_attachment = Attachment.STATUS.sin_identificar
        mesa_attachment = None
        testigo = None

        # Si no logramos consolidar una identificación vemos si hay un reporte de problemas.
        status_count = attachment.status_count(Identificacion.STATUS.problema)
        for mesa_id, cantidad, cuantos_csv in status_count:
            if cantidad >= settings.MIN_COINCIDENCIAS_IDENTIFICACION_PROBLEMA:
                # Tomo como "muestra" alguna de las que tienen problemas.
                identificacion_con_problemas = attachment.identificaciones.filter(
                    status=Identificacion.STATUS.problema
                ).first()
                # Confirmo el problema porque varios reportaron problemas.
                problema = Problema.confirmar_problema(identificacion=identificacion_con_problemas)
                status_attachment = Attachment.STATUS.problema

    # me acuerdo la mesa anterior por si se esta pasando a sin_identificar
    mesa_anterior = attachment.mesa

    # Identifico el attachment.
    # Notar que esta identificación podría estar sumando al attachment a una mesa que ya tenga.
    # Eso es correcto.
    # También podría estar haciendo pasar una attachment identificado al estado sin_identificar,
    # porque ya no está más vigente alguna identificación que antes sí.
    attachment.status = status_attachment
    attachment.mesa = mesa_attachment
    attachment.identificacion_testigo = testigo
    attachment.save(update_fields=['mesa', 'status', 'identificacion_testigo'])
    logger.info(
        'consolid. identificación',
        attachment=attachment.id,
        testigo=getattr(testigo, 'id', None),
        status=status_attachment
    )
    # si el attachment pasa de tener una mesa a no tenerla, entonces hay que invalidar
    # todo lo que se haya cargado para las MesaCategoria de la mesa que perdió su attachment
    if mesa_anterior and not mesa_attachment:
        mesa_anterior.invalidar_asignacion_attachment()


@transaction.atomic
def consumir_novedades_identificacion():
    a_procesar = Identificacion.objects.select_for_update().filter(procesada=False)
    # OJO - aca precomputar los ids_a_procesar es importante
    # ver comentario en consumir_novedades_carga()
    ids_a_procesar = list(a_procesar.values_list('id', flat=True).all())

    attachments_con_novedades = Attachment.objects.filter(
        identificaciones__in=ids_a_procesar
    ).distinct()
    for attachment in attachments_con_novedades:
        consolidar_identificaciones(attachment)

    # Todas procesadas
    procesadas = a_procesar.filter(id__in=ids_a_procesar).update(procesada=True)
    return procesadas


@transaction.atomic
def consumir_novedades_carga():
    a_procesar = Carga.objects.select_for_update().filter(procesada=False)
    ids_a_procesar = list(a_procesar.values_list('id', flat=True).all())
    # OJO - aca precomputar los ids_a_procesar es importante
    # si en lugar de hacer esto, al final se ejecuta
    #    a_procesar.update(procesada=True)
    # entonces se pasa a procesadas **todas** las cargas que tuvieren procesada=False
    # **al final** del proceso.
    #
    # En particular, si se detecta a un fiscal como troll, se pasan todas sus cargas a
    # invalidada=True y procesada=False, para que **la siguiente** consolidacion de cargas
    # recompute el estado de las MesaCategoria.
    # Pero también podría pasar que entren nuevas cargas mientras se ejecuta la consolidación.
    # En ambos casos, es importante que se respete que esas cargas están pendientes de proceso.
    #
    # Técnicamente, por más que se haga el SELECT arriba, si se pone
    #    a_procesar.update(procesada=True)
    # el SQL generado por Django es de la forma
    #    UPDATE carga SET procesada=True WHERE procesada=False
    # considera **la condición** del SELECT, no su resultado.
    # Al obtener los ids, se fuerza a que el SQL sea así:
    #    UPDATE carga SET procesada=True WHERE id in [...lista_precalculada_de_ids...]
    #
    # Carlos Lombardi, 2019.07.24
    mesa_categorias_con_novedades = MesaCategoria.objects.filter(
        cargas__in=ids_a_procesar
    ).distinct()
    for mesa_categoria_con_novedades in mesa_categorias_con_novedades:
        consolidar_cargas(mesa_categoria_con_novedades)

    # Todas procesadas
    procesadas = a_procesar.filter(id__in=ids_a_procesar).update(procesada=True)
    return procesadas

@transaction.atomic
def liberar_mesacategorias_y_attachments():
    """
    Toma a los fiscales cuya última tarea haya sido asignada más de
    `settings.TIMEOUT_TAREAS` minutos atrás y:
    - No se la desasinga para no perder el trabajo que va a hacer cuando haga el submit.
    - Pero sí le baja la cantidad de asignaciones a la mesacategoría y los attachments para que queden
    postergados por demasiado tiempo.
    """
    desde = timezone.now() - timedelta(minutes=settings.TIMEOUT_TAREAS)
    fiscales_con_timeout = Fiscal.objects.select_for_update(skip_locked=True).filter(
        asignacion_ultima_tarea__lt=desde)
    for fiscal in fiscales_con_timeout:
        if fiscal.attachment_asignado:
            fiscal.attachment_asignado.desasignar_a_fiscal()
        elif fiscal.mesa_categoria_asignada:
            fiscal.mesa_categoria_asignada.desasignar_a_fiscal()
        fiscal.resetear_timeout_asignacion_tareas()

def consumir_novedades():
    return (consumir_novedades_identificacion(), 
        consumir_novedades_carga(),
        liberar_mesacategorias_y_attachments()
    )


@receiver(post_save, sender=Attachment)
def actualizar_orden_de_carga(sender, instance=None, created=False, **kwargs):
    if instance.mesa and instance.identificacion_testigo:
        # Un nuevo attachment para una mesa ya identificada
        # (es decir, con orden de carga ya definido) la vuelve a actualizar.
        a_actualizar = MesaCategoria.objects.filter(mesa=instance.mesa)
        for mc in a_actualizar:
            mc.actualizar_orden_de_carga()
