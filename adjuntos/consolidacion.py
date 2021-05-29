from django.conf import settings
import structlog
from adjuntos.models import Attachment, Identificacion
from elecciones.models import Carga, MesaCategoria
from fiscales.models import Fiscal
from django.db import transaction
from django.db.models import Count, Q
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_save
from problemas.models import Problema
from antitrolling.efecto import (
    efecto_scoring_troll_asociacion_attachment, efecto_scoring_troll_confirmacion_carga
)
from sentry_sdk import capture_message

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
        if cargas_csv.exists():
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
        if cargas_csv.exists():
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


@transaction.atomic
def consolidar_cargas_sin_antitrolling(mesa_categoria):
    """
    Consolida todas las cargas de la MesaCategoria parámetro.

    El efecto antitrolling se trabaja por separado para hacerlo
    por fuera de la transacción y evitar deadlocks.
    """
    statuses_que_permiten_analizar_carga_total = [
        MesaCategoria.STATUS.sin_cargar,
        MesaCategoria.STATUS.parcial_consolidada_dc,
        MesaCategoria.STATUS.parcial_consolidada_csv
    ]

    # Por lo pronto el status es sin_cargar.
    status_resultante = MesaCategoria.STATUS.sin_cargar
    carga_testigo_resultante = None

    # Obtengo todas las cargas actualmente válidas para mesa_categoria.
    cargas = mesa_categoria.cargas.filter(invalidada=False)

    # Si no hay cargas, no sigo.
    if not cargas.exists():
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
    return status_resultante


def consolidar_cargas(mesa_categoria):
    """
    Consolida todas las cargas de la MesaCategoria parámetro y computa el efecto antitrolling.
    """
    statuses_que_requieren_computar_efecto_trolling = [
        MesaCategoria.STATUS.parcial_consolidada_dc,
        MesaCategoria.STATUS.total_consolidada_dc
    ]
    status_resultante = consolidar_cargas_sin_antitrolling(mesa_categoria)

    # Esto lo hacemos fuera de la transición para evitar deadlock (ver #337).
    if status_resultante in statuses_que_requieren_computar_efecto_trolling:
        efecto_scoring_troll_confirmacion_carga(mesa_categoria)


@transaction.atomic
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
                Problema.confirmar_problema(identificacion=identificacion_con_problemas)
                status_attachment = Attachment.STATUS.problema


    # me acuerdo la mesa anterior por si se esta pasando a sin_identificar
    mesa_anterior = attachment.mesa

    for attachment in attachment.with_children():
        # si tiene hijos se asigna la misma mesa.

        # Identifico el attachment y potencialmente sus attachment hijos.
        # Notar que esta identificación podría estar sumando al attachment a una mesa que ya tenga.
        # Eso es correcto.
        # También podría estar haciendo pasar una attachment identificado al estado sin_identificar,
        # porque ya no está más vigente alguna identificación que antes sí.
        attachment.status = status_attachment
        attachment.mesa = mesa_attachment
        if attachment.parent is None:
            attachment.identificacion_testigo = testigo
        attachment.save(update_fields=['mesa', 'status', 'identificacion_testigo'])
        logger.info(
            'Consolid. identificación',
            attachment=attachment.id,
            testigo=getattr(attachment.identificacion_testigo, 'id', None),
            status=status_attachment
        )

    # Si el attachment pasa de tener una mesa a no tenerla, entonces hay que invalidar
    # todo lo que se haya cargado para las MesaCategoria de la mesa que perdió su attachment.
    if mesa_anterior and not mesa_attachment:
        mesa_anterior.invalidar_asignacion_attachment()


def consumir_novedades_identificacion(cant_por_iteracion=None):
    ahora = timezone.now()
    desde = ahora - timedelta(minutes=settings.TIMEOUT_CONSOLIDACION)
    with transaction.atomic():
        # Lo hacemos en una transacción para no competir con otros consolidadores.
        a_procesar = Identificacion.objects.select_for_update(
            skip_locked=True
        ).filter(
            Q(tomada_por_consolidador__isnull=True) | Q(tomada_por_consolidador__lt=desde),
            procesada=False
        )
        if cant_por_iteracion:
            a_procesar = a_procesar[0:cant_por_iteracion]
        # OJO - acá precomputar los ids_a_procesar es importante
        # ver comentario en consumir_novedades_carga()
        ids_a_procesar = set(a_procesar.values_list('id', flat=True))
        Identificacion.objects.filter(id__in=list(ids_a_procesar)).update(tomada_por_consolidador=ahora)

    attachments_con_novedades = Attachment.objects.filter(
        identificaciones__in=ids_a_procesar
    ).distinct()
    con_error = set()

    for attachment in attachments_con_novedades:
        # FIXME: explicitar las excepciones que pueden ocurrir.
        try:
            consolidar_identificaciones(attachment)
        except Exception as e:
            # Logueamos la excepción y continuamos.
            capture_message(
                f"""
                Excepción {e} al procesar la identificación {attachment.id if attachment else None}.
                """
            )
            logger.error(
                'Identificación',
                attachment=attachment.id if attachment else None,
                error=str(e)
            )
            # Eliminamos los ids de las identificaciones que no se procesaron
            # para no marcarlas como procesada=True.
            identificaciones_ids = set(attachment.identificaciones.all().values_list('id',flat=True))
            con_error |= (ids_a_procesar & identificaciones_ids)
            ids_a_procesar -= identificaciones_ids


    # Todas procesadas (hay que seleccionar desde Identificacion porque 'a_procesar' ya fue sliceado).
    procesadas = Identificacion.objects.filter(
        id__in=list(ids_a_procesar)
    ).update(
        procesada=True,
        tomada_por_consolidador=None
    )
    # Las que tuvieron error no están procesadas pero se liberan.
    if con_error:
        Identificacion.objects.filter(id__in=list(con_error)).update(tomada_por_consolidador=None)

    return procesadas


def consumir_novedades_carga(cant_por_iteracion=None):
    ahora = timezone.now()
    desde = ahora - timedelta(minutes=settings.TIMEOUT_CONSOLIDACION)
    with transaction.atomic():
        # Lo hacemos en una transacción para no competir con otros consolidadores.
        a_procesar = Carga.objects.select_for_update(
            skip_locked=True
        ).filter(
            Q(tomada_por_consolidador__isnull=True) | Q(tomada_por_consolidador__lt=desde),
            procesada=False,
        )
        if cant_por_iteracion:
            a_procesar = a_procesar[0:cant_por_iteracion]
        ids_a_procesar = list(a_procesar.values_list('id', flat=True).all())
        Carga.objects.filter(id__in=ids_a_procesar).update(tomada_por_consolidador=ahora)
    # OJO - acá precomputar los ids_a_procesar es importante. Ver (*) al final de este doc para detalles.

    mesa_categorias_con_novedades = MesaCategoria.objects.filter(
        cargas__in=ids_a_procesar
    ).distinct()
    con_error = []

    for mesa_categoria_con_novedades in mesa_categorias_con_novedades:
        try:
            consolidar_cargas(mesa_categoria_con_novedades)
        except Exception as e:
            # Logueamos la excepción y continuamos.
            capture_message(
                f"""
                Excepción {e} al procesar la mesa-categoría
                {mesa_categoria_con_novedades.id if mesa_categoria_con_novedades else None}.
                """
            )
            logger.error(
                'Carga',
                mesa_categoria=mesa_categoria_con_novedades.id if mesa_categoria_con_novedades else None,
                error=str(e)
            )

            try:
                # Eliminamos los ids de las cargas que no se procesaron
                # para no marcarlas como procesada=True.
                for carga in mesa_categoria_con_novedades.cargas.all():
                    if carga.id in ids_a_procesar:
                        # Podría ser que la que generó la novedad sea otra carga de la mesacat.
                        ids_a_procesar.remove(carga.id)
                        con_error.append(carga.id)
            except Exception as e:
                capture_message(
                    f"""
                    Excepción {e} al manejar la excepción de la mesa-categoría
                    {mesa_categoria_con_novedades.id if mesa_categoria_con_novedades else None}.
                    """
                )
                logger.error(
                    'Carga (excepción)',
                    mesa_categoria=mesa_categoria_con_novedades.id if mesa_categoria_con_novedades else None,
                    error=str(e)
                )

    # Todas procesadas (hay que seleccionar desde Carga porque 'a_procesar' ya fue sliceado).
    procesadas = Carga.objects.filter(
        id__in=ids_a_procesar
    ).update(
        procesada=True, tomada_por_consolidador=None
    )
    # Las que tuvieron error no están procesadas pero se liberan.
    if con_error:
        Carga.objects.filter(id__in=con_error).update(tomada_por_consolidador=None)

    return procesadas


def liberar_mesacategorias_y_attachments():
    """
    Para la documentación ver a la función a la que se llama.
    """
    Fiscal.liberar_mesacategorias_y_attachments()


def consumir_novedades(cant_por_iteracion=None):
    """
    Recibe un parámetro que indica cuántos elementos procesar en cada iteración.
    Esto permite que muchas novedades de un tipo (eg, identificación)
    no impidan el procesamiento de las de otro tipo (eg, carga).
    None se interpreta como sin límite.
    """
    liberar_mesacategorias_y_attachments()
    return (
        consumir_novedades_identificacion(cant_por_iteracion),
        consumir_novedades_carga(cant_por_iteracion)
    )


@receiver(post_save, sender=Attachment)
def actualizar_orden_de_carga(sender, instance=None, created=False, **kwargs):
    if instance.mesa and instance.identificacion_testigo:
        # Un nuevo attachment para una mesa ya identificada
        # (es decir, con coeficiente de orden de carga ya definido) la vuelve a actualizar.
        a_actualizar = MesaCategoria.objects.filter(mesa=instance.mesa)
        for mc in a_actualizar:
            mc.actualizar_coeficiente_para_orden_de_carga()

# (*) Explicación de por qué es necesario obtener los ids de las cargas:
#
# Si en lugar de hacer esto, al final se ejecuta
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
