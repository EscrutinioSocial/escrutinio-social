import pytest

from elecciones.tests.factories import (
    SeccionFactory, CategoriaFactory
)
from scheduling.models import PrioridadScheduling


def test_configuracion_categoria(db):
    categoria=CategoriaFactory(prioridad=15)
    prioridades = PrioridadScheduling.objects.filter(categoria=categoria)
    assert prioridades.count() == 1 
    assert prioridades.first().prioridad == 15
    categoria.prioridad = 21
    categoria.save(update_fields=['prioridad'])
    prioridades = PrioridadScheduling.objects.filter(categoria=categoria)
    assert prioridades.count() == 1
    assert prioridades.first().prioridad == 21
    categoria.prioridad = None
    categoria.save(update_fields=['prioridad'])
    prioridades = PrioridadScheduling.objects.filter(categoria=categoria)
    assert prioridades.count() == 0

    categoria_2 = CategoriaFactory()
    prioridades = PrioridadScheduling.objects.filter(categoria=categoria)
    assert prioridades.count() == 0
