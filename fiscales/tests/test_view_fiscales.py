from django.urls import reverse
from http import HTTPStatus

from elecciones.tests.test_resultados import fiscal_client, setup_groups
from elecciones.tests.factories import (
    FiscalFactory,
    SeccionFactory,
)
from django.contrib.auth.models import Group
from fiscales.models import Fiscal
from fiscales.forms import ReferidoForm, EnviarEmailForm


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


def test_enviar_email_get(fiscal_client, admin_user):
    fiscales_ids = ','.join(str(f.id) for f in FiscalFactory.create_batch(2))
    url = f"{reverse('enviar-email')}?ids={fiscales_ids}"
    session = fiscal_client.session
    session.update({
        'enviar_email_asunto': 'foo',
        'enviar_email_template': '{{ foo }}',
    })
    session.save()

    response = fiscal_client.get(url)
    assert response.status_code == 200
    form = response.context['form']
    assert isinstance(form, EnviarEmailForm)
    assert 'Enviar Email a 2 fiscales' in response.content.decode('utf8')
    assert form.initial['asunto'] == 'foo'
    assert form.initial['template'] == '{{ foo }}'


def test_enviar_email_post(fiscal_client, admin_user, mailoutbox, settings):
    settings.DEFAULT_FROM_EMAIL = 'lio@messi.com'
    f = FiscalFactory(nombres='Diego Armando')
    f.agregar_dato_de_contacto('email', '10@diego.com')
    data = {'asunto': 'hola', 'template': '<p>Hola {{ fiscal.nombres }}</p>'}
    url = f"{reverse('enviar-email')}?ids={f.id}"
    response = fiscal_client.post(url, data)

    # se guardan variables de session
    assert fiscal_client.session.get('enviar_email_asunto') == 'hola'
    assert fiscal_client.session.get('enviar_email_template') == '<p>Hola {{ fiscal.nombres }}</p>'

    assert response.status_code == 302
    assert len(mailoutbox) == 1
    m = mailoutbox[0]
    assert m.subject == 'hola'
    assert 'Hola Diego Armando' in m.body   # text version
    html = m.alternatives[0][0]             # html version
    assert '<p>Hola Diego Armando</p>' in html
    assert html.startswith('<!doctype html>\n<html>\n  <head>\n')
    assert m.from_email == 'lio@messi.com'
    assert m.to == ['10@diego.com']