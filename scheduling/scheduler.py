from django.db import transaction
from constance import config
from django.conf import settings
from adjuntos.models import Attachment
from elecciones.models import MesaCategoria
from .models import ColaCargasPendientes, count_active_sessions


def scheduler(reconstruir_la_cola=False):
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
    cota_inferior_largo = max(count_active_sessions(), config.COTA_INFERIOR_COLA_TAREAS)
    long_cola = int(cota_inferior_largo * config.FACTOR_LARGO_COLA_POR_USUARIOS_ACTIVOS) - largo_cola

    mc_con_carga_pendiente = MesaCategoria.objects.con_carga_pendiente(for_update=False)
    attachments_sin_identificar = Attachment.objects.sin_identificar(for_update=False)

    cant_fotos = attachments_sin_identificar.count()
    cant_cargas = mc_con_carga_pendiente.count()

    identificaciones = iter(attachments_sin_identificar.priorizadas())
    cargas = iter(mc_con_carga_pendiente.ordenadas_por_prioridad_batch())

    nuevas, k, num_cargas, num_idents = [], orden_inicial, 0, 0

    for j in range(long_cola):

        # Si no hay nada por agregar terminamos el loop.
        if cant_fotos == 0 and cant_cargas == 0:
            break

        # Encolamos una mc si es lo único que hay disponible, o
        # si hay "suficientemente menos" fotos que cargas, donde
        # "suficientemente menos" involucra el multiplicador `COEFICIENTE_IDENTIFICACION_VS_CARGA`.
        turno_mc = (
            (cant_cargas > 0 and cant_fotos == 0) or
            cant_fotos < cant_cargas * config.COEFICIENTE_IDENTIFICACION_VS_CARGA
        )

        if turno_mc:
            # Mantenemos el invariante que `cant_cargas >=0` y si
            # estamos en este punto sabemos que `cant_cargas > 0`.
            mc = next(cargas)
            cant_cargas -= 1

            cant_unidades = settings.MIN_COINCIDENCIAS_CARGAS
            # Si ya está consolidada por CSV hay que hacer una carga menos.
            if mc.status in [MesaCategoria.STATUS.parcial_consolidada_csv, MesaCategoria.STATUS.total_consolidada_csv]:
                cant_unidades = settings.MIN_COINCIDENCIAS_CARGAS - 1
            # Si está en conflicto sólo necesitamos una carga más.
            elif mc.status in [MesaCategoria.STATUS.parcial_en_conflicto, MesaCategoria.STATUS.total_en_conflicto]:
                cant_unidades = 1

            for i in range(cant_unidades):
                # Encolo tantas unidades como haga falta.
                nuevas.append(
                    ColaCargasPendientes(
                        mesa_categoria=mc,
                        orden=k,
                        numero_carga=i,
                        distrito=mc.mesa.distrito
                    )
                )
                k += 1

            num_cargas += 1
            continue

        # Toca encolar foto. El chequeo `cant_fotos > 0` sólo tiene sentido
        # si `config.COEFICIENTE_IDENTIFICACION_CARGA <= 0`.
        if not turno_mc and cant_fotos > 0:
            foto = next(identificaciones)
            cant_fotos -= 1

            cant_unidades = settings.MIN_COINCIDENCIAS_IDENTIFICACION
            # Si hay alguna identificación asumimos que sólo falta una para consolidar.
            if foto.identificaciones.exists():
                cant_unidades = 1

            for i in range(cant_unidades):
                nuevas.append(
                    ColaCargasPendientes(
                        attachment=foto,
                        orden=k,
                        numero_carga=i,
                        distrito=foto.distrito_preidentificacion
                    )
                )
                k += 1

            num_idents += 1

    with transaction.atomic():
        if reconstruir_la_cola:
            ColaCargasPendientes.vaciar()
        ColaCargasPendientes.objects.bulk_create(nuevas, ignore_conflicts=True)

    return (k - orden_inicial, num_cargas, num_idents)
