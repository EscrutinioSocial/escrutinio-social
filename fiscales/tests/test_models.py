import pytest
from django.db.utils import IntegrityError
from django.urls import reverse
from elecciones.tests.factories import (
    CargaFactory,
    CategoriaFactory,
    FiscalFactory,
    MesaCategoriaFactory,
    OpcionFactory,
    VotoMesaReportadoFactory,
)
from elecciones.models import Opcion, MesaCategoria
from fiscales.models import CodigoReferido



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
    f.crear_codigo_de_referidos()
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


def test_datos_previos_parcial(db):
    o1 = OpcionFactory(tipo=Opcion.TIPOS.metadata, orden=1)
    o2 = OpcionFactory(orden=2)
    cat1 = CategoriaFactory(opciones=[o1, o2])

    # tengo una consolidacion parcial
    mc = MesaCategoriaFactory(categoria=cat1, status=MesaCategoria.STATUS.parcial_consolidada_dc)
    carga = CargaFactory(mesa_categoria=mc, tipo='total')
    VotoMesaReportadoFactory(carga=carga, opcion=o1, votos=10)
    VotoMesaReportadoFactory(carga=carga, opcion=o2, votos=12)
    mc.carga_testigo = carga
    mc.save()

    # si pedimos datos previos para realizar una carga total, los de consolidados parciales vienen
    assert mc.datos_previos('total') == {o1.id: 10, o2.id: 12}


def test_datos_previos_desde_metadata(db):
    o1 = OpcionFactory(tipo=Opcion.TIPOS.metadata, orden=1)
    o2 = OpcionFactory(orden=2)
    cat1 = CategoriaFactory(opciones=[o1, o2])

    mc = MesaCategoriaFactory(categoria=cat1, status=MesaCategoria.STATUS.total_consolidada_dc)
    carga = CargaFactory(mesa_categoria=mc, tipo='total')
    VotoMesaReportadoFactory(carga=carga, opcion=o1, votos=10)
    VotoMesaReportadoFactory(carga=carga, opcion=o2, votos=12)

    # otra categoria incluye la misma metadata.
    o2 = OpcionFactory(orden=2)
    cat2 = CategoriaFactory(opciones=[o1, o2])
    mc2 = MesaCategoriaFactory(categoria=cat2, mesa=mc.mesa)

    # esa mesa categoria incluye la metadata ya cargada en mc1
    assert mc2.datos_previos('parcial') == {o1.id: 10}
    assert mc2.datos_previos('total') == {o1.id: 10}
