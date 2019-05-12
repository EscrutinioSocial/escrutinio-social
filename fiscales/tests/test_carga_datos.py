import pytest
from django.urls import reverse
from elecciones.tests.factories import (
    VotoMesaReportadoFactory,
    EleccionFactory,
    AttachmentFactory,
    MesaFactory,
    OpcionFactory,
    CircuitoFactory,
)
from elecciones.models import Mesa, VotoMesaReportado, MesaEleccion
from elecciones.tests.test_resultados import fiscal_client          # noqa


def test_elegir_acta_sin_mesas(fiscal_client):
    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert 'No hay actas para cargar por el momento' in response.content.decode('utf8')


def test_elegir_acta_mesas_redirige(db, fiscal_client):

    assert Mesa.objects.count() == 0
    assert VotoMesaReportado.objects.count() == 0
    c = CircuitoFactory()
    e1 = EleccionFactory()
    e2 = EleccionFactory()

    m1 = AttachmentFactory(mesa__eleccion=[e1], mesa__lugar_votacion__circuito=c).mesa
    e2 = EleccionFactory()
    m2 = AttachmentFactory(mesa__eleccion=[e1, e2], mesa__lugar_votacion__circuito=c).mesa

    assert m1.orden_de_carga == 1
    assert m2.orden_de_carga == 2

    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert response.status_code == 302
    assert response.url == reverse('mesa-cargar-resultados', args=[e1.id, m1.numero])

    # como m1 queda en periodo de "taken" (aunque no se haya ocupado aun)
    # se pasa a la siguiente mesa
    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert response.status_code == 302
    assert response.url == reverse('mesa-cargar-resultados', args=[e1.id, m2.numero])

    # se carga esa eleccion
    VotoMesaReportadoFactory(mesa=m2, eleccion=e1, opcion=e1.opciones.first(), votos=1)

    # FIX ME . El periodo de taken deberia ser *por eleccion*.
    # en este escenario donde esta lockeado la mesa para la eleccion 1, pero no se está
    # cargando la mesa 2, un dataentry queda idle
    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert response.status_code == 200   # no hay actas

    m2.taken = None
    m2.save()
    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert response.status_code == 302
    assert response.url == reverse('mesa-cargar-resultados', args=[e2.id, m2.numero])


def test_elegir_acta_prioriza_por_tamaño_circuito(db, fiscal_client):
    e1 = EleccionFactory()

    m1 = AttachmentFactory(mesa__eleccion=[e1]).mesa
    m2 = AttachmentFactory(mesa__eleccion=[e1]).mesa
    m3 = AttachmentFactory(mesa__eleccion=[e1]).mesa
    # creo otras mesas asociadas a los circuitos
    c1 = m1.lugar_votacion.circuito
    c2 = m2.lugar_votacion.circuito
    c3 = m3.lugar_votacion.circuito

    MesaFactory.create_batch(
        3,
        eleccion=[e1],
        lugar_votacion__circuito=c1
    )
    MesaFactory.create_batch(
        10,
        eleccion=[e1],
        lugar_votacion__circuito=c2
    )
    MesaFactory.create_batch(
        5,
        eleccion=[e1],
        lugar_votacion__circuito=c3
    )
    assert c1.electores == 400
    assert c2.electores == 1100
    assert c3.electores == 600
    assert m1.orden_de_carga == m2.orden_de_carga == m3.orden_de_carga == 1
    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert response.status_code == 302
    assert response.url == reverse('mesa-cargar-resultados', args=[e1.id, m2.numero])
    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert response.status_code == 302
    assert response.url == reverse('mesa-cargar-resultados', args=[e1.id, m3.numero])
    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert response.status_code == 302
    assert response.url == reverse('mesa-cargar-resultados', args=[e1.id, m1.numero])


def test_carga_mesa_redirige_a_siguiente(db, fiscal_client):
    o = OpcionFactory(es_contable=True)
    e1 = EleccionFactory(opciones=[o])
    e2 = EleccionFactory(opciones=[o])
    m1 = AttachmentFactory(mesa__eleccion=[e1, e2]).mesa

    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert response.url == reverse('mesa-cargar-resultados', args=[e1.id, m1.numero])
    # response = fiscal_client.get(url)
    response = fiscal_client.post(response.url, {
        'form-0-opcion': str(o.id),
        'form-0-votos': str(m1.electores),
        'form-TOTAL_FORMS': '1',
        'form-INITIAL_FORMS': '0',
        'form-MIN_NUM_FORMS': '1',
        'form-MAX_NUM_FORMS': '1000',
    })
    assert response.status_code == 302
    assert response.url == reverse('mesa-cargar-resultados', args=[e2.id, m1.numero])

    response = fiscal_client.post(response.url, {
        'form-0-opcion': str(o.id),
        'form-0-votos': str(m1.electores),
        'form-TOTAL_FORMS': '1',
        'form-INITIAL_FORMS': '0',
        'form-MIN_NUM_FORMS': '1',
        'form-MAX_NUM_FORMS': '1000',
    })
    assert response.status_code == 302
    assert response.url == reverse('elegir-acta-a-cargar')


def test_chequear_resultado(db, fiscal_client):
    o = OpcionFactory(es_contable=True)
    e1 = EleccionFactory(opciones=[o])
    mesa = MesaFactory(eleccion=[e1])
    me = MesaEleccion.objects.get(eleccion=e1, mesa=mesa)
    assert me.confirmada is False

    VotoMesaReportadoFactory(opcion=o, mesa=mesa, eleccion=e1, votos=1)
    response = fiscal_client.get(reverse('chequear-resultado'))
    assert response.status_code == 302
    assert response.url == reverse('chequear-resultado-mesa', args=[e1.id, mesa.numero])
    me.confirmada = True
    me.save()
    response = fiscal_client.get(reverse('chequear-resultado'))
    assert response.status_code == 200
    assert 'No hay actas cargadas para verificar por el momento' in response.content.decode('utf8')


def test_chequear_resultado_mesa(db, fiscal_client):
    opcs = OpcionFactory.create_batch(3, es_contable=True)
    e1 = EleccionFactory(opciones=opcs)
    e2 = EleccionFactory(opciones=opcs)
    mesa = MesaFactory(eleccion=[e1, e2])
    me = MesaEleccion.objects.get(eleccion=e1, mesa=mesa)
    assert me.confirmada is False
    votos1 = VotoMesaReportadoFactory(opcion=opcs[0], mesa=mesa, eleccion=e1, votos=1)
    votos2 = VotoMesaReportadoFactory(opcion=opcs[1], mesa=mesa, eleccion=e1, votos=2)
    votos3 = VotoMesaReportadoFactory(opcion=opcs[2], mesa=mesa, eleccion=e1, votos=1)

    # a otra eleccion
    VotoMesaReportadoFactory(opcion=opcs[2], mesa=mesa, eleccion=e2, votos=1)

    url = reverse('chequear-resultado-mesa', args=[e1.id, mesa.numero])
    response = fiscal_client.get(url)

    assert list(response.context['reportados']) == [votos1, votos2, votos3]

    response = fiscal_client.post(url, {'confirmar': 'confirmar'})
    assert response.status_code == 302
    assert response.url == reverse('chequear-resultado')
    me.refresh_from_db()
    assert me.confirmada is True


def test_chequear_resultado_eleccion_desactivada(db, fiscal_client):
    opcs = OpcionFactory.create_batch(3, es_contable=True)
    e1 = EleccionFactory(opciones=opcs)
    assert e1.activa is True
    mesa = MesaFactory(eleccion=[e1])
    url = reverse('chequear-resultado-mesa', args=[e1.id, mesa.numero])
    response = fiscal_client.get(url)
    assert response.status_code == 200
    e1.activa = False
    e1.save()
    response = fiscal_client.get(url)
    assert response.status_code == 404
