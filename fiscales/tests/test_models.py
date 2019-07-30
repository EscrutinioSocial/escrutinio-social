import pytest
from django.db.utils import IntegrityError
from django.urls import reverse
from elecciones.tests.factories import FiscalFactory
from fiscales.models import CodigoReferido, Fiscal


def test_fiscal_crea_codigo(db):
    FiscalFactory.create_batch(4)
    assert CodigoReferido.objects.count() == 4


def test_crear_codigo_desactiva_viejos(db):
    f = FiscalFactory()
    cod_original = CodigoReferido.objects.get()
    assert cod_original.activo is True
    nuevo = f.crear_codigo_de_referidos()
    assert nuevo.activo is True
    cod_original.refresh_from_db()
    assert cod_original.activo is False


def test_ultimo_codigo_url(db, settings, mocker):
    settings.FULL_SITE_URL = 'https://site.com'
    mocker.patch('fiscales.models.Fiscal.ultimo_codigo', return_value='D10S')
    f = FiscalFactory()
    assert f.ultimo_codigo_url() == 'https://site.com' + reverse('quiero-validar', args=['D10S'])


def test_fiscales_para_codigo(db):
    f = FiscalFactory()
    code_original = f.ultimo_codigo()
    # case unsensitive
    assert CodigoReferido.fiscales_para(code_original.lower()) == [(f, 100)]

    # por nombre y apellido. case unsensitive
    assert CodigoReferido.fiscales_para('otro', f.nombres.upper(), f.apellido.title()) == [(f, 75)]

    # codigo viejo
    nuevo = f.crear_codigo_de_referidos()
    assert CodigoReferido.fiscales_para(code_original) == [(f, 25)]

    # codigo invalido
    assert CodigoReferido.fiscales_para('NADA') == [(None, 100)]



def test_generar_codigo_check_unicidad(db, mocker):
    mocked_sample = mocker.patch('fiscales.models.random.sample', return_value=['0', '0', '0', '0'])
    f = FiscalFactory()
    # el primero tiene codigo 0000
    assert f.codigos_de_referidos.get().codigo == '0000'
    # el siguiente intenta 5 codigos.
    with pytest.raises(IntegrityError):
        FiscalFactory()
    assert mocked_sample.call_count == 6


