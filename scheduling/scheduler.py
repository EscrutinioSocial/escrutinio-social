from django.db import models, transaction
from django.db.models import Sum, Count, Q, F, ExpressionWrapper, PositiveIntegerField
from django.contrib.sessions.models import Session
from django.utils import timezone
from constance import config

from adjuntos.models import Identificacion
from elecciones.models import MesaCategoria, Carga, Categoria
from .models import ColaCargasPendientes, largo_cola

def count_active_sessions():
    sessions = Session.objects.filter(expire_date__gte=timezone.now()).count()
    return sessions

def scheduler():
    cota_inferior_largo = max(count_active_sessions(), config.COTA_INFERIOR_COLA)
    long_cola = int(cota_inferior_largo * config.FACTOR_LARGO_COLA_POR_USUARIOS_ACTIVOS) - largo_cola()
    
    orden = F('coeficiente_para_orden_de_carga')+F('prioridad_status')*100+F('cant_asignaciones_realizadas')*10
    mc_con_carga_pendiente = MesaCategoria.objects.con_carga_pendiente(
        for_update=False
    ).anotar_prioridad_status().annotate(
        orden = ExpressionWrapper(orden, output_field = PositiveIntegerField())
    ).order_by('orden','id')[:long_cola]

    (nuevas,k) = ([],0)
    for nueva in mc_con_carga_pendiente:
        nuevas.append(ColaCargasPendientes(mesa_categoria = nueva,orden = nueva.orden+k))
        k += 1

    ColaCargasPendientes.objects.bulk_create(nuevas, ignore_conflicts=True)
    
    return k
