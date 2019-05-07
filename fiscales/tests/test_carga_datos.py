from django.urls import reverse
from elecciones.tests.factories import (
    VotoMesaReportadoFactory,
    EleccionFactory,
    AttachmentFactory,
    MesaFactory,
    CircuitoFactory,
    ProblemaFactory
)
from elecciones.models import Mesa, VotoMesaReportado
from elecciones.tests.test_resultados import fiscal_client          # noqa


def test_elegir_resultados_sin_mesas(fiscal_client):
    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert 'No hay actas para cargar por el momento' in response.content.decode('utf8')


def test_elegir_resultados_mesas_redirige(db, fiscal_client):

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
    assert response.url == reverse('mesa-cargar-resultados', args=[e2.id, m2.id])
