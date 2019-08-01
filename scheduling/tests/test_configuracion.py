import pytest

from elecciones.tests.factories import (
    SeccionFactory, CategoriaFactory
)
from scheduling.models import PrioridadScheduling
from .utils_para_test import asignar_prioridades_standard

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


def test_configuracion_seccion(db):
    seccion = SeccionFactory(prioridad_hasta_2=1, prioridad_2_a_10=12)
    seccion_2 = SeccionFactory()
    prioridades = PrioridadScheduling.objects.filter(seccion=seccion)
    assert prioridades.count() == 2
    assert prioridades.filter(desde_proporcion=0).first().prioridad == 1
    assert prioridades.filter(desde_proporcion=0).first().hasta_cantidad is None
    assert prioridades.filter(desde_proporcion=2).first().prioridad == 12
    assert prioridades.filter(desde_proporcion=2).first().hasta_proporcion == 10
    prioridades = PrioridadScheduling.objects.filter(seccion=seccion_2)
    assert prioridades.count() == 0

    seccion.prioridad_hasta_2 = None
    seccion.prioridad_2_a_10 = 15
    seccion.prioridad_10_a_100 = 45
    seccion.save(update_fields=['prioridad_hasta_2', 'prioridad_2_a_10', 'prioridad_10_a_100'])
    prioridades = PrioridadScheduling.objects.filter(seccion=seccion)
    assert prioridades.count() == 2
    assert prioridades.filter(desde_proporcion=2).first().prioridad == 15
    assert prioridades.filter(desde_proporcion=10).first().prioridad == 45
    assert prioridades.filter(desde_proporcion=10).first().hasta_proporcion == 100

    seccion.prioridad_hasta_2 = 3
    seccion.cantidad_minima_prioridad_hasta_2 = 7
    seccion.save(update_fields=['prioridad_hasta_2', 'cantidad_minima_prioridad_hasta_2'])
    prioridades = PrioridadScheduling.objects.filter(seccion=seccion)
    assert prioridades.count() == 3
    assert prioridades.filter(desde_proporcion=0).first().prioridad == 3
    assert prioridades.filter(desde_proporcion=0).first().hasta_cantidad == 7
    assert prioridades.filter(desde_proporcion=2).first().prioridad == 15
    assert prioridades.filter(desde_proporcion=2).first().categoria is None
    assert prioridades.filter(desde_proporcion=10).first().prioridad == 45
    assert prioridades.filter(desde_proporcion=10).first().hasta_proporcion == 100



def test_configuracion_seccion_set_hasta_cantidad_no_prioridad(db, settings):
    asignar_prioridades_standard(settings)
    seccion = SeccionFactory(cantidad_minima_prioridad_hasta_2=9)
    prioridades = PrioridadScheduling.objects.filter(seccion=seccion)
    assert prioridades.count() == 1
    assert prioridades.filter(desde_proporcion=0).first().prioridad == \
        settings.PRIORIDADES_STANDARD_SECCION[0]['prioridad']
    assert prioridades.filter(desde_proporcion=0).first().hasta_cantidad == 9
