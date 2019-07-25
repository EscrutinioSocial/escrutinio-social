from unittest import mock

from fiscales.views import generar_codigo_confirmacion, generar_codigo_random
from elecciones.tests.factories import FiscalFactory


def test_generar_codigo_random(db):
    codigos = []
    for index in range(10):
        codigo = generar_codigo_confirmacion()
        assert codigo not in codigos
        codigos.append(codigo)
        FiscalFactory(referido_codigo=codigo)


def test_generar_codigo__check_unicidad(db):
    with mock.patch("fiscales.views.generar_codigo_random") as mocked_random:
        codigo_no_random = "pepe"
        FiscalFactory(referido_codigo=codigo_no_random)
        # lo hacemos si o si distinto
        codigo_a_devolver = codigo_no_random + "_addendum"
        mocked_random.side_effect = [codigo_no_random, codigo_a_devolver]
        codigo = generar_codigo_confirmacion()
        
        assert codigo == codigo_a_devolver
        mocked_random.call_count = 2