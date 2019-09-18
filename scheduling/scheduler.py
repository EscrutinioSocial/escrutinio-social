from django.db import models, transaction
from django.db.models import Sum, Count, Q, F, ExpressionWrapper, PositiveIntegerField
from django.contrib.sessions.models import Session
from django.utils import timezone
from constance import config
from django.conf import settings
from adjuntos.models import Attachment
from elecciones.models import MesaCategoria, Carga, Categoria
from .models import ColaCargasPendientes


def count_active_sessions():
    sessions = Session.objects.filter(expire_date__gte=timezone.now()).count()
    return sessions


@transaction.atomic
def scheduler():
    largo_cola = ColaCargasPendientes.largo_cola()
    ultimo = ColaCargasPendientes.objects.order_by('-orden').first()
    orden_inicial = ultimo.orden if ultimo else 0
    cota_inferior_largo = max(count_active_sessions(), config.COTA_INFERIOR_COLA)
    long_cola = int(cota_inferior_largo * config.FACTOR_LARGO_COLA_POR_USUARIOS_ACTIVOS) - largo_cola

    # El campo calculado `orden` busca definir un orden total sobre
    # las cargas pendientes. La idea subyacente es un orden
    # lexicográfico de los siguientes ítems:
    #
    # (1) importancia de la mesa categoría de acuerdo a la categoría y
    # la zona geográfica (teniendo en cuenta cargas de esa zona).
    # (2) la prioridad del status (menos cargas menos prioridad)
    # (3) la cantidad de asignaciones ya hechas (penalizamos levemente las
    # mesas categorías que asignamos más veces).
    #
    # Los coeficientes buscan asegurar ese orden lexicográfico; no
    # multiplicamos (1) porque ya de por sí suelen tener números altos.
    orden = (F('coeficiente_para_orden_de_carga') +
             F('prioridad_status') * 100 +
             F('cant_asignaciones_realizadas') * 10)

    mc_con_carga_pendiente = MesaCategoria.objects.con_carga_pendiente(
        for_update=False
    ).anotar_prioridad_status().annotate(
        orden=ExpressionWrapper(orden, output_field=PositiveIntegerField())
    ).order_by('orden', 'id')

    """
    Elige la siguiente acción a ejecutarse de acuerdo a los siguientes criterios:

    - Si sólo hay actas sin cargar la accion será identificar una de ellas.

    - Si sólo hay mesas con carga pendiente (es decir, que tienen categorias sin cargar),
      se elige una por orden de prioridad.

    - Si hay tanto mesas como actas pendientes, se elige identicar
      si el tamaño de la cola de identificaciones pendientes es X veces el tamaño de la
      cola de carga (siendo X la variable config.COEFICIENTE_IDENTIFICACION_VS_CARGA).

    - En otro caso, no hay nada para hacer
    """
    attachments = Attachment.objects.sin_identificar(for_update=False)

    cant_fotos = attachments.count()
    cant_cargas = mc_con_carga_pendiente.count()

    identificaciones = iter(attachments.priorizadas())
    cargas = iter(mc_con_carga_pendiente)
    
    (nuevas, k, num_cargas, num_idents) = ([], orden_inicial, 0, 0)
    
    for j in range(long_cola):
        mc = next(cargas, None)
        foto = next(identificaciones, None)

        # si no hay nada por agregar terminamos el loop.
        if mc is None and foto is None:
            break

        turno_mesa = j % config.COEFICIENTE_IDENTIFICACION_VS_CARGA != 0
        if mc and (turno_mesa or foto is None):
            cant_unidades = settings.MIN_COINCIDENCIAS_CARGAS
            # Si ya está consolidada por CSV hay que hacer una carga menos.
            if mc.status in [MesaCategoria.STATUS.parcial_consolidada_csv, MesaCategoria.STATUS.total_consolidada_csv]:
                cant_unidades = settings.MIN_COINCIDENCIAS_CARGAS - 1
            # Si está en conflicto sólo necesitamos una carga más.
            elif mc.status in [MesaCategoria.STATUS.parcial_en_conflicto, MesaCategoria.STATUS.total_en_conflicto]:
               cant_unidades = 1

            for i in range(cant_unidades):
                # Encolo tantas unidades como haga falta.
                nuevas.append(ColaCargasPendientes(mesa_categoria=mc, orden=k, numero_carga=i))
                k += 1

            num_cargas += 1
            continue

        # si hay una foto y toca encolar foto ó si no hay mesa
        if foto and (not turno_mesa or mc is None):
            nuevas.append(ColaCargasPendientes(attachment=foto, orden=k))
            k += 1
            num_idents += 1
            continue

        
    ColaCargasPendientes.objects.bulk_create(nuevas, ignore_conflicts=True)

    return (k - orden_inicial, num_cargas, num_idents)
