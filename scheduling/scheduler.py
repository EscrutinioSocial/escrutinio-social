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
    """
    Puebla lo cola de elementos a asignar de acuerdo al siguiente criterio:

    - Si sólo hay actas sin cargar la accion será identificar una de ellas.

    - Si sólo hay mesas con carga pendiente (es decir, que tienen categorias sin cargar),
      se elige una por orden de prioridad.

    - Si hay tanto mesas como actas pendientes, se elige identicar
      si el tamaño de la cola de identificaciones pendientes es X veces el tamaño de la
      cola de carga (siendo X la variable config.COEFICIENTE_IDENTIFICACION_VS_CARGA).

    - En otro caso, no hay nada para hacer.
    """
    largo_cola = ColaCargasPendientes.largo_cola()
    ultimo = ColaCargasPendientes.objects.order_by('-orden').first()
    orden_inicial = ultimo.orden if ultimo else 0
    cota_inferior_largo = max(count_active_sessions(), config.COTA_INFERIOR_COLA)
    long_cola = int(cota_inferior_largo * config.FACTOR_LARGO_COLA_POR_USUARIOS_ACTIVOS) - largo_cola

    mc_con_carga_pendiente = MesaCategoria.objects.con_carga_pendiente(for_update=False)
    attachments_sin_identificar = Attachment.objects.sin_identificar(for_update=False)

    cant_fotos = attachments_sin_identificar.count()
    cant_cargas = mc_con_carga_pendiente.count()

    identificaciones = iter(attachments_sin_identificar.priorizadas())
    cargas = iter(mc_con_carga_pendiente.ordenadas_por_prioridad_batch())
    
    nuevas, k, num_cargas, num_idents = [], orden_inicial, 0, 0
    
    for j in range(long_cola):
        mc = next(cargas, None)
        foto = next(identificaciones, None)

        # Si no hay nada por agregar terminamos el loop.
        if mc is None and foto is None:
            break

        # Encolamos una mc si es lo único que hay disponible, o 
        # si hay "suficientemente menos" fotos que cargas, donde
        # "suficientemente menos" involucra el multiplicador `COEFICIENTE_IDENTIFICACION_VS_CARGA`.
        turno_mc = (cant_cargas and not cant_fotos or
            cant_fotos < cant_cargas * config.COEFICIENTE_IDENTIFICACION_VS_CARGA)

        if mc and (turno_mc or foto is None):
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
            cant_cargas = max(0, cant_cargas - 1)  # No debería hacerse negativo, pero por las dudas.
            continue

        # Si hay una foto y toca encolar foto o si no hay mesa.
        if foto and (not turno_mc or mc is None):
            nuevas.append(ColaCargasPendientes(attachment=foto, orden=k))
            k += 1
            num_idents += 1
            cant_fotos = max(0, cant_fotos - 1)  # No debería hacerse negativo, pero por las dudas.
            continue

    ColaCargasPendientes.objects.bulk_create(nuevas, ignore_conflicts=True)

    return (k - orden_inicial, num_cargas, num_idents)
