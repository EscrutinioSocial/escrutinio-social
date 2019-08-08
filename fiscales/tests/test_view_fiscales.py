import json

from django.urls import reverse
from http import HTTPStatus
from urllib import parse

from elecciones.tests.test_resultados import fiscal_client, setup_groups
from elecciones.tests.factories import (
    DistritoFactory,    
    FiscalFactory,
    SeccionFactory,
)
from django.contrib.auth.models import Group
from fiscales.models import Fiscal
from fiscales.forms import ReferidoForm

from elecciones.models import Seccion


QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT = {
    "nombres": "Diego Armando",
    "apellido": "Maradona",
    "dni": "14276579",
    "distrito": "1",
    "referente_nombres": "Hugo Rafael",
    "referente_apellido": "Chavez",
    "referido_por_codigo": "BLVR",
    "telefono_local": "42631145",
    "telefono_area": "11",
    "email": "diego@maradona.god.ar",
    "email_confirmacion": "diego@maradona.god.ar",
    "password": "diego1986",
    "password_confirmacion": "diego1986",
}


def test_choice_home_admin(db, client, admin_user):
    # no logueado
    response = client.get('')
    assert response.status_code == 302
    assert response.url == reverse('login')

    client.login(username=admin_user.username, password='password')
    response = client.get('')
    assert response.status_code == 302
    assert response.url == reverse('admin:index')


def test_choice_home_validador_o_nada(db, admin_user, fiscal_client):
    # admin es validador
    response = fiscal_client.get('')
    assert response.status_code == 302
    assert response.url == reverse('siguiente-accion')

    # admin no es ni validador ni staff
    g = Group.objects.get(name='validadores')
    admin_user.groups.remove(g)
    admin_user.is_staff = False
    admin_user.save()
    response = fiscal_client.get('')
    assert response.status_code == 302
    assert response.url == reverse('bienvenido')


def test_quiero_validar__camino_feliz(db, client):
    url_quiero_validar = reverse('quiero-validar')
    response = client.get(url_quiero_validar)
    assert response.status_code == HTTPStatus.OK

    assert not Fiscal.objects.exists()

    seccion = SeccionFactory()
    request_data = construir_request_data(seccion)
    response = client.post(url_quiero_validar, request_data)

    assert Fiscal.objects.count() == 1
    _assert_fiscal_cargado_correctamente(seccion)

    fiscal = _get_fiscal()
    # se setea el fiscal
    assert client.session['fiscal_id'] == fiscal.id
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('quiero-validar-gracias')


def test_quiero_validar_gracias(db, client):
    f = FiscalFactory()
    s = client.session
    s['fiscal_id'] = f.id
    s.save()
    response = client.get(reverse('quiero-validar-gracias'))
    assert response.context['fiscal'] == f
    assert f.ultimo_codigo_url() in response.content.decode('utf8')


def test_quiero_validar__error_validacion(db, client):
    # hacemos un test que muestre que al validar nos quedamos en la misma página y no se crea un fiscal
    # la lógica de validación más fina del form la hacemos en el test_forms_fiscales
    url_quiero_validar = reverse('quiero-validar')
    response = client.get(url_quiero_validar)
    assert response.status_code == HTTPStatus.OK

    assert not Fiscal.objects.exists()

    seccion = SeccionFactory()
    request_data = construir_request_data(seccion)
    del(request_data["dni"])
    response = client.post(url_quiero_validar, request_data)

    assert response.status_code == HTTPStatus.OK
    assert response.context['form'].errors

    assert not Fiscal.objects.exists()


def test_quiero_validar_con_codigo(db, client):
    url_quiero_validar = reverse('quiero-validar', args=['xxxx'])
    response = client.get(url_quiero_validar)
    assert response.context['form'].initial['referido_por_codigo'] == 'xxxx'


def _get_fiscal():
    return Fiscal.objects.filter(
        referido_por_codigos=QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['referido_por_codigo']
    ).first()


def _assert_fiscal_cargado_correctamente(seccion):
    fiscal = _get_fiscal()

    assert fiscal
    assert len(fiscal.referido_por_codigos) == 4

    assert fiscal.nombres == QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['nombres']
    assert fiscal.apellido == QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['apellido']
    assert fiscal.dni == QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['dni']

    assert fiscal.seccion == seccion

    assert fiscal.referente_apellido == QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['referente_apellido']
    assert fiscal.referente_nombres == QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['referente_nombres']
    assert fiscal.referido_por_codigos == QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['referido_por_codigo']

    assert QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['telefono_local'] in fiscal.telefonos[0]
    assert fiscal.telefonos[0].startswith(QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT['telefono_area'])

    assert fiscal.user is not None
    assert fiscal.user.password is not None


def construir_request_data(seccion):
    data = QUIERO_SER_FISCAL_REQUEST_DATA_DEFAULT.copy()
    data["seccion"] = seccion.id
    data["seccion_autocomplete"] = seccion.id
    return data


def test_referidos_muestra_link_y_referidos(fiscal_client, admin_user):
    fiscal = admin_user.fiscal
    referidos_ids = {f.id for f in FiscalFactory.create_batch(2, referente=fiscal)}

    # otros fiscales no afectan
    FiscalFactory(referente=FiscalFactory())

    assert set(fiscal.referidos.values_list('id', flat=True)) == referidos_ids

    response = fiscal_client.get(reverse('referidos'))
    assert response.status_code == 200
    content = response.content.decode('utf8')
    form = response.context['form']

    assert isinstance(form, ReferidoForm)
    assert form.initial['url'] == fiscal.ultimo_codigo_url()
    assert set(response.context['referidos'].values_list('id', flat=True)) == referidos_ids
    assert str(response.context['referidos'][0]) in content
    assert str(response.context['referidos'][1]) in content


def test_referidos_post_regenera_link(fiscal_client, admin_user, mocker):
    crear_mock = mocker.patch('fiscales.models.Fiscal.crear_codigo_de_referidos')
    response = fiscal_client.post(
        reverse('referidos'), data={'link': ''}
    )
    assert response.status_code == 200
    assert crear_mock.call_count == 1


def test_referidos_post_confirma_conoce(fiscal_client, admin_user):
    fiscal = admin_user.fiscal
    referidos_ids = [f.id for f in FiscalFactory.create_batch(2, referente=fiscal)]
    assert fiscal.referidos.filter(referencia_confirmada=True).count() == 0
    response = fiscal_client.post(
        reverse('referidos'), data={'conozco': '', 'referido': referidos_ids}
    )
    assert response.status_code == 200
    assert fiscal.referidos.filter(referencia_confirmada=True).count() == 2


def test_autocomplete_seccion__sin_seccion_especifica(db, client):
    SeccionFactory.create_batch(20)

    url = reverse("autocomplete-seccion-simple")

    response = client.get(url)
    response_data = json.loads(response.content)
    resultados = response_data["results"]

    # nos devuelve los 10 resultados
    assert len(resultados) == 10
    assert response_data["pagination"]["more"]


def test_autocomplete_seccion__camino_feliz(db, client):
    tam_batch = 10
    secciones = SeccionFactory.create_batch(tam_batch)
    distrito = secciones[0].distrito

    # pedimos el nombre completo de una seccion, el match debiese ser único
    # (a menos que pidamos "Seccion 7" y existan cosas como "Seccion 7x",  "Sección 7xx", etc)
    query = secciones[tam_batch - 1].nombre

    response = _hacer_call_seccion_autocomplete(client, q=query, distrito=distrito)
    response_data = json.loads(response.content)
    resultados = response_data["results"]

    assert len(resultados) == 1
    assert query in resultados[0]['text']


def test_autocomplete_seccion__dos_distritos(db, client):
    distrito1, distrito2 = DistritoFactory.create_batch(2)
    SeccionFactory(distrito=distrito1)
    SeccionFactory(distrito=distrito1)
    SeccionFactory(distrito=distrito1)
    SeccionFactory(distrito=distrito2)
    SeccionFactory(distrito=distrito2)

    query = "Sección"

    response = _hacer_call_seccion_autocomplete(client, q=query)
    response_data = json.loads(response.content)
    resultados = response_data["results"]

    # sin distrito, me trae todo
    assert len(resultados) == 5

    for resultado in resultados:
        assert query in resultado["text"]

    response = _hacer_call_seccion_autocomplete(client, q=query, distrito=distrito1)
    response_data = json.loads(response.content)
    resultados = response_data["results"]

    # trae solo las 3 del distrito 1
    assert len(resultados) == 3

    for resultado in resultados:
        assert query in resultado["text"]


def _hacer_call_seccion_autocomplete(client, q=None, distrito=None):
    params = {}
    if distrito:
        forward = f'{{"distrito": "{distrito.id}"}}'
        params["forward"] = forward
    if q:
        params["q"] = q
    query_string = parse.urlencode(params)
    url = reverse("autocomplete-seccion-simple") + "?" + query_string
    return client.get(url)
