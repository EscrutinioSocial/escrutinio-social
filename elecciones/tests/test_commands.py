from elecciones.tests.factories import CategoriaFactory, MesaFactory, DistritoFactory
from elecciones.models import Opcion, CategoriaOpcion
from django.conf import settings
from django.core.management import call_command


def test_calcular_prioridad_de_mesas(db, django_assert_num_queries):
    m1 = MesaFactory(
        lugar_votacion__circuito__prioridad=5,
        lugar_votacion__circuito__seccion__prioridad=9
    )
    d = DistritoFactory(prioridad=3)
    m2, m3 = MesaFactory.create_batch(
        2,
        lugar_votacion__circuito__seccion__distrito=d,
        lugar_votacion__circuito__prioridad=2,
    )
    with django_assert_num_queries(2):
        call_command('calcular_prioridad_de_mesas')
    m1.refresh_from_db()
    m2.refresh_from_db()
    m3.refresh_from_db()
    assert m1.prioridad == 95
    assert m2.prioridad == m3.prioridad == 302


def test_setup_opciones(db):
    assert not Opcion.objects.exists()
    c = CategoriaFactory(opciones=[])
    call_command('setup_opciones_basicas')
    assert Opcion.objects.get(**settings.OPCION_BLANCOS)
    assert Opcion.objects.get(**settings.OPCION_TOTAL_VOTOS)
    assert Opcion.objects.get(**settings.OPCION_TOTAL_SOBRES)
    assert Opcion.objects.get(**settings.OPCION_NULOS)
    assert c.opciones.count() == 4
