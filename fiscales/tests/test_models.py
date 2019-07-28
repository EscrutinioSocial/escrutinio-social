import pytest
from django.db.utils import IntegrityError

from elecciones.tests.factories import FiscalFactory


from fiscales.models import CodigoReferido


def test_fiscal_crea_codigo(db):
    FiscalFactory.create_batch(4)
    assert CodigoReferido.objects.count() == 4


def test_generar_codigo_check_unicidad(db, mocker):
    mocked_sample = mocker.patch('fiscales.models.random.sample', return_value=['0', '0', '0', '0'])
    f = FiscalFactory()
    # el primero tiene codigo 0000
    assert f.codigos_de_referidos.get().codigo == '0000'
    # el siguiente intenta 5 codigos.
    with pytest.raises(IntegrityError):
        FiscalFactory()
    assert mocked_sample.call_count == 6
