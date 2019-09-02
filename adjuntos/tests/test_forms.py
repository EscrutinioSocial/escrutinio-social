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


@pytest.mark.skip('Verificar si está obsoleto respecto del comportamiento de la UI.')
def test_identificacion_nuevo_choices(db):
    d = Distrito.objects.get()      # 'Distrito único', lo crea una migracion
    d2 = DistritoFactory(nombre='otro distrito')
    MesaFactory(), MesaFactory()

    form = IdentificacionForm()

    # los querysets (opciones validas) están vacíos, excepto distrito
    distrito_qs = form.fields['distrito'].queryset
    distritos = list(Distrito.objects.all())
    assert list(distrito_qs) == distritos

    ## Por ahora no tenemos más selects en los siguientes niveles.
    # seccion_qs = form.fields['seccion'].queryset
    # assert list(seccion_qs) == list(Seccion.objects.all())
    # circuito_qs = form.fields['circuito'].queryset
    # assert list(circuito_qs) == list(Circuito.objects.all())
    # mesa_qs = form.fields['mesa'].queryset
    # assert list(mesa_qs) == list(Mesa.objects.all())

    # pero las opciones para seccion, circuito, mesa están vacias
    opciones_base = [('', '---------')]
    # y se completan dinámicamente cuando se elige el padre
    opciones_d = [(d2.id, str(d2)), (d.id, str(d))]
    
    assert list(form.fields['distrito'].choices) == opciones_base + opciones_d

    ## Por ahora no tenemos más selects en los siguientes niveles.
    # assert list(form.fields['seccion'].choices) == opciones_base + [(o.id,str(o)) for o in list(seccion_qs)]
    # assert list(form.fields['circuito'].choices) == opciones_base + [(o.id,str(o)) for o in list(circuito_qs)]
    # assert list(form.fields['mesa'].choices) == opciones_base + [(o.id,str(o)) for o in list(mesa_qs)]


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
