from django.db import models, transaction
from django.db.models import Sum, Count, Q, F, ExpressionWrapper, PositiveIntegerField
from django.contrib.sessions.models import Session
from django.utils import timezone
from constance import config
from django.conf import settings
from adjuntos.models import Identificacion
from elecciones.models import MesaCategoria, Carga, Categoria
from .models import ColaCargasPendientes


def count_active_sessions():
    sessions = Session.objects.filter(expire_date__gte=timezone.now()).count()
    return sessions


@transaction.atomic
def scheduler():
    cota_inferior_largo = max(count_active_sessions(), config.COTA_INFERIOR_COLA)
    long_cola = int(cota_inferior_largo * config.FACTOR_LARGO_COLA_POR_USUARIOS_ACTIVOS) - ColaCargasPendientes.largo_cola()

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
    ).order_by('orden', 'id')[:long_cola]

    (nuevas, k) = ([], 0)
    for nueva in mc_con_carga_pendiente:
        cant_unidades = settings.MIN_COINCIDENCIAS_CARGAS
        # Si ya está consolidada por CSV hay que hacer una carga menos.
        if nueva.status in [MesaCategoria.STATUS.parcial_consolidada_csv, MesaCategoria.STATUS.total_consolidada_csv]:
            cant_unidades -= 1
        # Si está en conflicto sólo necesitamos una carga más.
        elif nueva.status in [MesaCategoria.STATUS.parcial_en_conflicto, MesaCategoria.STATUS.total_en_conflicto]:
            cant_unidades = 1

        for i in range(cant_unidades):
            # Encolo tantas unidades como haga falta.
            nuevas.append(ColaCargasPendientes(mesa_categoria=nueva, orden=nueva.orden + k + i))
            k += 1

    ColaCargasPendientes.objects.bulk_create(nuevas, ignore_conflicts=True)

    return k
