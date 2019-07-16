from django.conf import settings
from adjuntos.models import Attachment, Identificacion
from elecciones.models import Carga, MesaCategoria
from django.db import transaction
from django.db.models import Subquery, Count


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

    cargas_agrupadas_por_firma = cargas.values('firma').annotate(
                                            count=Count('firma')
                                        ).order_by('-count')

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


def consolidar_cargas(mesa_categoria):
    """
    Consolida todas las cargas de la MesaCategoria parámetro.
    """

    # Por lo pronto el status es sin_cargar.
    status_resultante = MesaCategoria.STATUS.sin_cargar
    carga_testigo_resultante = None

    # Obtengo todas las cargas actualmente válidas para mesa_categoria.
    cargas = mesa_categoria.cargas.filter(valida=True)

    # Si no hay cargas, no sigo.
    if cargas.count() == 0:
        mesa_categoria.actualizar_status(status_resultante, carga_testigo_resultante)
        return

    # Hay cargas. A continuación voy probando los distintos status de mayor a menor.

    # Analizo las totales.
    cargas_totales = cargas.filter(tipo=Carga.TIPOS.total)
    if cargas_totales.count() > 0:
        status_resultante, carga_testigo_resultante = \
            consolidar_cargas_por_tipo(cargas_totales, Carga.TIPOS.total)
        mesa_categoria.actualizar_status(status_resultante, carga_testigo_resultante)
        return

    # Por último analizo las parciales.
    cargas_parciales = cargas.filter(tipo=Carga.TIPOS.parcial)
    if cargas_parciales.count() > 0:
        status_resultante, carga_testigo_resultante = \
            consolidar_cargas_por_tipo(cargas_parciales, Carga.TIPOS.parcial)
        mesa_categoria.actualizar_status(status_resultante, carga_testigo_resultante)


def consolidar_identificaciones(attachment):
    """
    Consolida todas las identificaciones del Attachment parámetro.
    Deja una como testigo, si están dadas las condiciones.
    Si hay una identificación con origen csv, ésa es la testigo.

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
    status_count = attachment.status_count()

    mesa_id_consolidada = None
    for mesa_id, status, cantidad, cuantos_csv in status_count:
        if (
            status == Identificacion.STATUS.identificada and (
                cantidad >= settings.MIN_COINCIDENCIAS_IDENTIFICACION or
                cuantos_csv > 0
            )
        ):
            mesa_id_consolidada = mesa_id
            break

    if mesa_id_consolidada:
        # Consolidamos una mesa, ya sea por CSV o por multicoincidencia.

        identificaciones_correctas = attachment.identificaciones.filter(
            mesa_id=mesa_id_consolidada, status=Identificacion.STATUS.identificada
        )

        identificacion_con_csv = identificaciones_correctas.filter(
            source=Identificacion.SOURCES.csv
        ).first()

        # Si hay una de CSV, es la testigo. Si no, cualquiera del resto.
        testigo = identificacion_con_csv if identificacion_con_csv else identificaciones_correctas.first()

        # Identifico el attachment.
        status_attachment = testigo.status
        mesa_attachment = testigo.mesa

        # TODO - para reportar trolls
        # sumar 200 a scoring de los usuarios que identificaron el acta diferente
    else:
        status_attachment = Attachment.STATUS.sin_identificar
        mesa_attachment = None
        testigo = None

    # Identifico el attachment.
    # Notar que esta identificación podría estar sumando al attachment a una mesa que ya tenga.
    # Eso es correcto.
    # También podría estar haciendo pasar una attachment identificado al estado sin_identificar,
    # porque ya no está más vigente alguna identificación que antes sí.
    attachment.status = status_attachment
    attachment.mesa = mesa_attachment
    attachment.identificacion_testigo = testigo
    attachment.save(update_fields=['mesa', 'status', 'identificacion_testigo'])


@transaction.atomic
def consumir_novedades_identificacion():
    a_procesar = Identificacion.objects.select_for_update().filter(procesada=False)
    attachments_con_novedades = Attachment.objects.filter(
        identificaciones__in=Subquery(a_procesar.values('id'))
    ).distinct()
    for attachment in attachments_con_novedades:
        consolidar_identificaciones(attachment)
    a_procesar.update(procesada=True)


@transaction.atomic
def consumir_novedades_carga():
    a_procesar = Carga.objects.select_for_update().filter(procesada=False)

    mesa_categorias_con_novedades = MesaCategoria.objects.filter(
        cargas__in=Subquery(a_procesar.values('id'))
    ).distinct()
    for mesa_categoria_con_novedades in mesa_categorias_con_novedades:
        consolidar_cargas(mesa_categoria_con_novedades)

    # Todas procesadas
    a_procesar.update(procesada=True)


def consumir_novedades():
    consumir_novedades_identificacion()
    consumir_novedades_carga()
