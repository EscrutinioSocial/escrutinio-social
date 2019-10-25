import pytest
from django.http import QueryDict
from django.core.files.uploadedfile import SimpleUploadedFile
from adjuntos.forms import IdentificacionForm, PreIdentificacionForm, BaseUploadForm

from elecciones.tests.factories import (
    DistritoFactory,
    SeccionFactory,
    CircuitoFactory,
    MesaFactory
)
from elecciones.models import (
    Distrito,
    Seccion,
    Circuito,
    Mesa
)


def test_identificacion_valida_jerarquia(db):
    m1 = MesaFactory()
    m2 = MesaFactory()
    form = IdentificacionForm({
        'mesa': m1.numero,
        'circuito': m1.circuito.numero,
        'seccion': m1.circuito.seccion.numero,
        'distrito': m1.circuito.seccion.distrito.id,
    })
    assert form.is_valid()


def test_identificacion_valida_seccion_no_corresponde_a_distrito(db):
    m1 = MesaFactory()
    m2 = MesaFactory()
    form = IdentificacionForm({
        'mesa': m1.numero,
        'circuito': m1.circuito.numero,
        'seccion': m1.circuito.seccion.numero,
        'distrito': DistritoFactory().id,
    })
    assert not form.is_valid()
    assert form.errors['seccion'] == ['Esta sección no pertenece al distrito']


def test_identificacion_valida_si_circuito_no_corresponde_a_seccion(db):
    m1 = MesaFactory()
    m2 = MesaFactory()
    form = IdentificacionForm({
        'mesa': m1.numero,
        'circuito': m1.circuito.numero,
        'seccion': m2.circuito.seccion.numero,
        'distrito': m2.circuito.seccion.distrito.id,
    })
    assert not form.is_valid()
    assert form.errors['circuito'] == ['Este circuito no pertenece a la sección']


def test_identificacion_valida_si_mesa_no_corresponde_a_circuito(db):
    m1 = MesaFactory()
    m2 = MesaFactory()
    form = IdentificacionForm({
        'mesa': m1.numero,
        'circuito': m2.circuito.numero,
        'seccion': m2.circuito.seccion.numero,
        'distrito': m2.circuito.seccion.distrito.id,
    })
    assert not form.is_valid()
    assert form.errors['mesa'] == ['Esta mesa no pertenece al circuito']

    form = IdentificacionForm({
        'mesa': m1.id,
        'circuito': m1.circuito.id,
        'seccion': m2.circuito.seccion.id,
        'distrito': m2.circuito.seccion.distrito.id,
    })
    assert not form.is_valid()
    assert form.errors['circuito'] == ['Este circuito no pertenece a la sección']


@pytest.mark.parametrize('size, valid', [
    (9, True),
    (10, True),
    (11, False),
])
def test_base_form_file_size(settings, size, valid):
    settings.MAX_UPLOAD_SIZE = 10
    file = SimpleUploadedFile('data.csv', b'0' * size)
    file_data = QueryDict(mutable=True)
    file_data.update(file_field=file)
    form = BaseUploadForm(files=file_data)
    assert form.is_valid() is valid


def test_preidentificacion_nok(db):
    m1 = MesaFactory()
    m2 = MesaFactory()
    form = PreIdentificacionForm({
        'circuito': m1.circuito.id,
        'seccion': m2.circuito.seccion.id,
        'distrito': m2.circuito.seccion.distrito.id,
    })
    assert not form.is_valid()
    assert form.errors['circuito'] == ['Este circuito no pertenece a la sección']

def test_preidentificacion_ok(db):
    m1 = MesaFactory()
    form = PreIdentificacionForm({
        'circuito': m1.circuito.id,
        'seccion': m1.circuito.seccion.id,
        'distrito': m1.circuito.seccion.distrito.id,
    })
    assert form.is_valid()


def test_preidentificacion_parcial_ok(db):
    m1 = MesaFactory()
    form = PreIdentificacionForm({
        'circuito': m1.circuito.id,
        'seccion': m1.circuito.seccion.id,
        'distrito': m1.circuito.seccion.distrito.id
    })
    assert form.is_valid()

    form = PreIdentificacionForm({
        'seccion': m1.circuito.seccion.id,
        'distrito': m1.circuito.seccion.distrito.id
    })
    assert form.is_valid()

    form = PreIdentificacionForm({
        'distrito': m1.circuito.seccion.distrito.id
    })
    assert form.is_valid()

def test_identificacion_busqueda_de_mesa(db):
    c1 = CircuitoFactory()

    # se crea la mesa 123 para chequear que no debe devolver nunca esta mesa
    # si se buscan alternativas de la 23
    m0 = MesaFactory(numero='123', circuito=c1)
    m1 = MesaFactory(numero='23', circuito=c1)

    # el usuario ingresa 023, le devuelve la mesa 23
    form = IdentificacionForm({
        'mesa': '023',
        'circuito': c1.numero,
        'seccion': c1.seccion.numero,
        'distrito': c1.seccion.distrito.id,
    })
    assert form.is_valid()
    assert form.cleaned_data['mesa'] == m1

    # el usuario ingresa 23/8, como no existe le devuelve la mesa 2
    form = IdentificacionForm({
        'mesa': '23/8',
        'circuito': c1.numero,
        'seccion': c1.seccion.numero,
        'distrito': c1.seccion.distrito.id,
    })
    assert form.is_valid()
    assert form.cleaned_data['mesa'] == m1

    # el usuario ingresa 23 como no existe le devuelve la mesa 23
    form = IdentificacionForm({
        'mesa': '23',
        'circuito': c1.numero,
        'seccion': c1.seccion.numero,
        'distrito': c1.seccion.distrito.id,
    })
    assert form.is_valid()
    assert form.cleaned_data['mesa'] == m1

    # se crea la mesa 23/8
    m2 = MesaFactory(numero='23/8', circuito=c1)

    # el usuario ingresa 00023/8, existe 23/8 le devuelve la mesa 23/8
    form = IdentificacionForm({
        'mesa': '00023/8',
        'circuito': c1.numero,
        'seccion': c1.seccion.numero,
        'distrito': c1.seccion.distrito.id,
    })
    assert form.is_valid()
    assert form.cleaned_data['mesa'] == m2

    # el usuario ingresa 23/8, existe 23/8 le devuelve la mesa 23/8
    form = IdentificacionForm({
        'mesa': '23/8',
        'circuito': c1.numero,
        'seccion': c1.seccion.numero,
        'distrito': c1.seccion.distrito.id,
    })
    assert form.is_valid()
    assert form.cleaned_data['mesa'] == m2

    # el usuario ingresa 00023/4, como no existe le devuelve la mesa 23
    form = IdentificacionForm({
        'mesa': '00023/4',
        'circuito': c1.numero,
        'seccion': c1.seccion.numero,
        'distrito': c1.seccion.distrito.id,
    })
    assert form.is_valid()
    assert form.cleaned_data['mesa'] == m1

    # el usuario ingresa '  0023/8 ', le devuelve la mesa 23/8
    form = IdentificacionForm({
        'mesa': '  0023/8 ',
        'circuito': c1.numero,
        'seccion': c1.seccion.numero,
        'distrito': c1.seccion.distrito.id,
    })
    assert form.is_valid()
    assert form.cleaned_data['mesa'] == m2

    # el usuario ingresa 5, como no existe le devuelve error
    form = IdentificacionForm({
        'mesa': '5',
        'circuito': c1.numero,
        'seccion': c1.seccion.numero,
        'distrito': c1.seccion.distrito.id,
    })
    assert not form.is_valid()
    assert form.errors['mesa'] == ['Esta mesa no pertenece al circuito']

    # buscar mesa en distrito 2 sin pasar circuito en el form
    d2 = DistritoFactory(numero='2')
    s2 = SeccionFactory(numero='2', distrito=d2)
    c2 = CircuitoFactory(numero='2', seccion=s2)
    m3 = MesaFactory(numero='24/8', circuito=c2)
    form = IdentificacionForm({
        'mesa': '0024/8',
        'seccion': s2.numero,
        'distrito': d2.id,
        'circuito': ''
    })
    assert form.is_valid()
    assert form.cleaned_data['mesa'] == m3

    # buscar mesa en distrito 2 sin pasar sección en el form
    form = IdentificacionForm({
        'mesa': '0024/8',
        'seccion': '',
        'distrito': d2.id,
        'circuito': c2.numero
    })
    assert form.is_valid()
    assert form.cleaned_data['mesa'] == m3

    # buscar mesa en distrito 2 sin pasar cricuito ni sección en el form
    form = IdentificacionForm({
        'mesa': '0024/8',
        'seccion': '',
        'distrito': d2.id,
        'circuito': ''
    })
    assert not form.is_valid()
    assert form.errors['seccion'] == ['Sección y/o circuito deben estar completos']
    assert form.errors['circuito'] == ['Sección y/o circuito deben estar completos']

def test_identificacion_de_mesa_circuito_numero_case_insensitive(db):
    c1 = CircuitoFactory(numero='1A')

    # mesa asociada al circuito 1A con mayúscula
    m1 = MesaFactory(circuito=c1)

    # el usuario ingresa '1a' en minúscula
    form = IdentificacionForm({
        'mesa': m1.numero,
        'circuito': '1a',
        'seccion': c1.seccion.numero,
        'distrito': c1.seccion.distrito.id,
    })
    assert form.is_valid()
    assert form.cleaned_data['mesa'] == m1

    c2 = CircuitoFactory(numero='23/B')
    # mesa asociada al circuito 23/B con mayúscula
    m2 = MesaFactory(circuito=c2)

    # el usuario ingresa '23/b' en minúscula
    form = IdentificacionForm({
        'mesa': m2.numero,
        'circuito': '23/b',
        'seccion': c2.seccion.numero,
        'distrito': c2.seccion.distrito.id,
    })
    assert form.is_valid()
    assert form.cleaned_data['mesa'] == m2
