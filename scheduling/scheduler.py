from django.db import models, transaction
from django.db.models import Sum, Count, Q, F, ExpressionWrapper, PositiveIntegerField
from django.contrib.sessions.models import Session
from django.utils import timezone
from constance import config

from adjuntos.models import Identificacion
from elecciones.models import MesaCategoria, Carga, Categoria
from .models import ColaCargaPendientes

def count_active_sessions():
    sessions = Session.objects.filter(expire_date__gte=timezone.now()).count()
    return sessions

def scheduler():
    largo_cola = int(count_active_sessions() * config.LARGO_COLA_USUARIOS_ACTIVOS)
    
    # lo que sigue es sólo ilustrativo
    orden = F('categoria__id')*100+F('mesa__id')*10+F('percentil')
    mc_con_carga_pendiente = MesaCategoria.objects.con_carga_pendiente(for_update=False).annotate(
        orden = ExpressionWrapper(orden, output_field = PositiveIntegerField())
    ).order_by('-orden')[:largo_cola]

    nuevas = [ColaCargaPendientes(mesaCategoria=m,orden=m.orden) for m in mc_con_carga_pendiente]

    ColaCargaPendientes.objects.bulk_create(nuevas, batch_size=largo_cola, ignore_conflicts=True)
    
    return len(nuevas)
