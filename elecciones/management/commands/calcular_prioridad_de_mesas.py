from django.core.management.base import BaseCommand
from elecciones.models import Mesa
from django.db.models import F


def update_prioridad(m):
    m.prioridad = 100 * m.d_prioridad + 10 * m.s_prioridad + m.c_prioridad
    return m


class Command(BaseCommand):
    help = (
        "Configura la prioridad de cada mesa en función de "
        "las prioridades de la respectiva jerarquía"
    )

    def handle(self, *args, **options):
        mesas = Mesa.objects.annotate(
            c_prioridad=F('circuito__prioridad'),
            s_prioridad=F('circuito__seccion__prioridad'),
            d_prioridad=F('circuito__seccion__distrito__prioridad'),
        )
        mesas = [update_prioridad(m) for m in mesas]
        Mesa.objects.bulk_update(mesas, ['prioridad'], batch_size=5000)
