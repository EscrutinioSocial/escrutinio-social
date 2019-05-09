from django.urls import reverse
from elecciones.tests.factories import (
    VotoMesaReportadoFactory,
    EleccionFactory,
    AttachmentFactory,
    MesaFactory,
    OpcionFactory,
    CircuitoFactory,
    ProblemaFactory
)
from elecciones.models import Mesa, VotoMesaReportado
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

    # como m1 queda en periodo de "taken" (aunque no se haya ocupado aun) se pasa a la siguiente mesa
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


def test_elegir_acta_prioriza_por_tamaño_seccion(db, fiscal_client):
    e1 = EleccionFactory()

    m1 = AttachmentFactory(mesa__eleccion=[e1]).mesa
    m2 = AttachmentFactory(mesa__eleccion=[e1]).mesa
    m3 = AttachmentFactory(mesa__eleccion=[e1]).mesa
    # creo otras mesas asociadas a las secciones
    s1 = m1.lugar_votacion.circuito.seccion
    s2 = m2.lugar_votacion.circuito.seccion
    s3 = m3.lugar_votacion.circuito.seccion

    MesaFactory.create_batch(
        3,
        eleccion=[e1],
        lugar_votacion__circuito__seccion=s1
    )
    MesaFactory.create_batch(
        10,
        eleccion=[e1],
        lugar_votacion__circuito__seccion=s2
    )
    MesaFactory.create_batch(
        5,
        eleccion=[e1],
        lugar_votacion__circuito__seccion=s3
    )
    assert s1.electores == 400
    assert s2.electores == 1100
    assert s3.electores == 600
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





