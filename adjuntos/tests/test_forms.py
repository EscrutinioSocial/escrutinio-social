from adjuntos.forms import IdentificacionForm
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


def test_identificacion_nuevo_choices(db):
    d = Distrito.objects.get()      # 'Distrito único', lo crea una migracion
    d2 = DistritoFactory(nombre='otro distrito')
    MesaFactory(), MesaFactory()

    form = IdentificacionForm()

    # los querysets (opciones validas) son todos los disponibles
    distrito_qs = form.fields['distrito'].queryset
    distritos = list(Distrito.objects.all())
    assert list(distrito_qs) == distritos
    seccion_qs = form.fields['seccion'].queryset
    assert list(seccion_qs) == list(Seccion.objects.all())
    circuito_qs = form.fields['circuito'].queryset
    assert list(circuito_qs) == list(Circuito.objects.all())
    mesa_qs = form.fields['mesa'].queryset
    assert list(mesa_qs) == list(Mesa.objects.all())

    # pero las opciones para seccion, circuito, mesa están vacias
    # y se completan a dinámicamente cuando se elige el padre
    opciones_base = [('', '---------')]
    opciones_d = [(d2.id, str(d2)), (d.id, str(d))]
    assert list(form.fields['distrito'].choices) == opciones_base + opciones_d
    assert list(form.fields['seccion'].choices) == opciones_base
    assert list(form.fields['circuito'].choices) == opciones_base
    assert list(form.fields['mesa'].choices) == opciones_base


def test_identificacion_valida_jerarquia(db):
    m1 = MesaFactory()
    m2 = MesaFactory()
    form = IdentificacionForm({
        'mesa': m1.id,
        'circuito': m1.circuito.id,
        'seccion': m1.circuito.seccion.id,
        'distrito': m1.circuito.seccion.distrito.id,
    })
    assert form.is_valid()


def test_identificacion_valida_seccion_no_corresponde_a_distrito(db):
    m1 = MesaFactory()
    m2 = MesaFactory()
    form = IdentificacionForm({
        'mesa': m1.id,
        'circuito': m1.circuito.id,
        'seccion': m1.circuito.seccion.id,
        'distrito': DistritoFactory(),
    })
    assert not form.is_valid()
    assert form.errors['seccion'] == ['Esta sección no pertenece al distrito']


def test_identificacion_valida_si_circuito_no_corresponde_a_seccion(db):
    m1 = MesaFactory()
    m2 = MesaFactory()
    form = IdentificacionForm({
        'mesa': m1.id,
        'circuito': m1.circuito.id,
        'seccion': m2.circuito.seccion.id,
        'distrito': m2.circuito.seccion.distrito.id,
    })
    assert not form.is_valid()
    assert form.errors['circuito'] == ['Este circuito no pertenece a la sección']


def test_identificacion_valida_si_mesa_no_corresponde_a_circuito(db):
    m1 = MesaFactory()
    m2 = MesaFactory()
    form = IdentificacionForm({
        'mesa': m1.id,
        'circuito': m2.circuito.id,
        'seccion': m2.circuito.seccion.id,
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




