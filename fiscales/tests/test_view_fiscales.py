from unittest import mock
from django.urls import reverse
from http import HTTPStatus

from elecciones.tests.factories import (
    FiscalFactory,
    SeccionFactory,
)

from fiscales.views import generar_codigo_confirmacion, generar_codigo_random
from fiscales.forms import QuieroSerFiscalForm
from fiscales.models import Fiscal

QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT = {
    "nombres": "Diego Armando",
    "apellido": "Maradona",
    "dni": "14276579",
    "distrito": "1",
    "referido_por_nombres": "Hugo Rafael",
    "referido_por_apellido": "Chavez",
    "referido_por_codigo": "BLVR",
    "telefono_local": "42631145",
    "telefono_area": "11",
    "email": "diego@maradona.god.ar",
    "email_confirmacion": "diego@maradona.god.ar",
    "password": "diego1986",
    "password_confirmacion": "diego1986",
}


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


def test_quiero_validar__camino_feliz(db, client):
    url_quiero_validar = reverse('quiero-validar')
    response = client.get(url_quiero_validar)
    assert response.status_code == HTTPStatus.OK

    fiscales_antes = Fiscal.objects.count()
    _assert_no_esta_fiscal_cargado_de_antemano()

    seccion = SeccionFactory()
    request_data = construir_request_data(seccion)
    response = client.post(url_quiero_validar, request_data)

    fiscales_despues = Fiscal.objects.count()
    assert fiscales_antes + 1 == fiscales_despues
    _assert_fiscal_cargado_correctamente(seccion)

    fiscal = _get_fiscal()
    url_gracias = reverse('quiero-validar-gracias', kwargs={'codigo_ref': fiscal.referido_codigo})

    assert HTTPStatus.FOUND == response.status_code
    assert url_gracias == response.url


def test_quiero_validar__error_validacion(db, client):
    # hacemos un test que muestre que al validar nos quedamos en la misma página y no se crea un fiscal
    # la lógica de validación más fina del form la hacemos en el test_forms_fiscales
    url_quiero_validar = reverse('quiero-validar')
    response = client.get(url_quiero_validar)
    assert response.status_code == HTTPStatus.OK

    fiscales_antes = Fiscal.objects.count()
    _assert_no_esta_fiscal_cargado_de_antemano()

    seccion = SeccionFactory()
    request_data = construir_request_data(seccion)
    del(request_data["dni"])
    response = client.post(url_quiero_validar, request_data)

    assert response.status_code == HTTPStatus.OK
    assert response.context['form'].errors

    fiscales_despues = Fiscal.objects.count()
    assert fiscales_antes == fiscales_despues
    _assert_no_esta_fiscal_cargado_de_antemano()


def _assert_no_esta_fiscal_cargado_de_antemano():
    fiscal = _get_fiscal()
    assert fiscal is None


def _get_fiscal():
    return Fiscal.objects.filter(
        referido_por_codigo=QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['referido_por_codigo']
    ).first()


def _assert_fiscal_cargado_correctamente(seccion):
    fiscal = _get_fiscal()

    assert fiscal
    assert fiscal.referido_codigo is not None
    assert len(fiscal.referido_codigo) == QuieroSerFiscalForm.CARACTERES_REF_CODIGO

    assert fiscal.nombres == QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['nombres']
    assert fiscal.apellido == QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['apellido']
    assert fiscal.dni == QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['dni']

    assert fiscal.seccion == seccion

    assert fiscal.referido_por_apellido == QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['referido_por_apellido']
    assert fiscal.referido_por_nombres == QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['referido_por_nombres']
    assert fiscal.referido_por_codigo == QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['referido_por_codigo']

    assert QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['telefono_local'] in fiscal.telefonos[0]
    assert fiscal.telefonos[0].startswith(QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['telefono_area'])

    assert fiscal.user is not None
    assert fiscal.user.password is not None


def construir_request_data(seccion):
    data = QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT.copy()
    data["seccion"] = seccion.id
    data["seccion_autocomplete"] = seccion.id
    return data
