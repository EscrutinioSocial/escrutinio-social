import json
import pytest
from django.db.models import Sum
from django.urls import reverse
from elecciones.models import Eleccion, Mesa
from elecciones.views import ResultadosEleccion, TOTAL, POSITIVOS
from .factories import (
    EleccionFactory,
    SeccionFactory,
    CircuitoFactory,
    MesaFactory,
    FiscalGeneralFactory,
    AttachmentFactory,
    VotoMesaReportadoFactory,
)




@pytest.fixture()
def carta_marina(db):
    """
    2 secciones con 2 circuitos y 2 mesas por circuito
    """
    s1, s2 = SeccionFactory.create_batch(2)
    c1, c2 = CircuitoFactory.create_batch(2, seccion=s1)
    c3, c4 = CircuitoFactory.create_batch(2, seccion=s2)
    return (MesaFactory(numero=1, lugar_votacion__circuito=c1, electores=100),
            MesaFactory(numero=2, lugar_votacion__circuito=c1, electores=100),
            MesaFactory(numero=3, lugar_votacion__circuito=c2, electores=120),
            MesaFactory(numero=4, lugar_votacion__circuito=c2, electores=120),
            MesaFactory(numero=5, lugar_votacion__circuito=c3, electores=90),
            MesaFactory(numero=6, lugar_votacion__circuito=c3, electores=90),
            MesaFactory(numero=7, lugar_votacion__circuito=c4, electores=90),
            MesaFactory(numero=8, lugar_votacion__circuito=c4, electores=90))


@pytest.fixture()
def fiscal_client(db, admin_user):
    """A Django test client logged in as an admin user."""
    from django.test.client import Client

    client = Client()
    FiscalGeneralFactory(user=admin_user)
    client.login(username=admin_user.username, password='password')
    return client


@pytest.fixture()
def url_resultados(carta_marina):
    return reverse('resultados-eleccion', args=[3])


def test_total_electores_en_eleccion(carta_marina):
    # la sumatoria de todas las mesas de la eleccion
    # nota: el factory de mesa indirectamente crea la eleccion con id=1 que es actual()
    assert Eleccion.objects.get(id=1).electores == 800


def test_electores_filtro_mesa(url_resultados, fiscal_client):
    mesa1 = Mesa.objects.get(numero=1)
    response = fiscal_client.get(url_resultados, {'mesa': mesa1.id})
    data = json.loads(response.content)
    assert f'<td title="Electores">{mesa1.electores} </td>' in data['metadata']

def test_electores_filtro_escuela(url_resultados, fiscal_client):
    mesa1 = Mesa.objects.get(numero=1)
    response = fiscal_client.get(url_resultados, {
        'lugarvotacion': mesa1.lugar_votacion.id})
    data = json.loads(response.content)
    assert f'<td title="Electores">{mesa1.electores} </td>' in data['metadata']


def test_electores_filtro_circuito(url_resultados, fiscal_client):
    mesa1 = Mesa.objects.get(numero=1)
    response = fiscal_client.get(url_resultados, {
        'circuito': mesa1.lugar_votacion.circuito.id})
    data = json.loads(response.content)
    assert '<td title="Electores">200 </td>' in data['metadata']


def test_electores_filtro_seccion(url_resultados, fiscal_client):
    mesa1 = Mesa.objects.get(numero=1)
    response = fiscal_client.get(url_resultados, {
        'seccion': mesa1.lugar_votacion.circuito.seccion.id})
    data = json.loads(response.content)
    assert '<td title="Electores">440 </td>' in data['metadata']


def test_electores_sin_filtro(url_resultados, fiscal_client):
    response = fiscal_client.get(url_resultados)
    data = json.loads(response.content)
    assert '<td title="Electores">800 </td>' in data['metadata']


def test_electores_sin_filtro(url_resultados, fiscal_client):
    response = fiscal_client.get(url_resultados)
    data = json.loads(response.content)
    assert '<td title="Electores">800 </td>' in data['metadata']


def test_resultados_parciales(carta_marina, fiscal_client):
    # resultados para mesa 1
    m1, _, m3, *_ = carta_marina
    url = reverse('resultados-eleccion', args=[3])
    eleccion = Eleccion.objects.get(id=1)
    o1, o2, o3 = eleccion.opciones.filter(partido__isnull=False)
    total = eleccion.opciones.get(nombre=TOTAL)
    pos = eleccion.opciones.get(nombre=POSITIVOS)
    VotoMesaReportadoFactory(opcion=o1, mesa=m1, votos=20)
    VotoMesaReportadoFactory(opcion=o2, mesa=m1, votos=30)
    VotoMesaReportadoFactory(opcion=o3, mesa=m1, votos=40)
    VotoMesaReportadoFactory(opcion=pos, mesa=m1, votos=80)
    # votaron 90/100 personas
    VotoMesaReportadoFactory(opcion=total, mesa=m1, votos=90)

    VotoMesaReportadoFactory(opcion=o1, mesa=m3, votos=30)
    VotoMesaReportadoFactory(opcion=o2, mesa=m3, votos=40)
    VotoMesaReportadoFactory(opcion=o3, mesa=m3, votos=50)
    VotoMesaReportadoFactory(opcion=pos, mesa=m3, votos=120)
    # votaron 120/120 personas
    VotoMesaReportadoFactory(opcion=total, mesa=m3, votos=120)

    response = fiscal_client.get(url)
    data = json.loads(response.content)
    tabla = data['content']
    assert f'<td id="votos_{o1.partido.id}"> 50</td>' in tabla
    assert f'<td id="votos_{o2.partido.id}"> 70</td>' in tabla
    assert f'<td id="votos_{o3.partido.id}"> 90</td>' in tabla
    assert f'<td id="votos_{o3.partido.id}"> 10</td>' in tabla



def test_mesa_orden(carta_marina):
    m1, m2, *_ = carta_marina
    AttachmentFactory(mesa=m1)
    assert m1.orden_de_carga == 1
    assert m2.orden_de_carga == 0
    AttachmentFactory(mesa=m2)
    assert m2.orden_de_carga == 2

def test_elegir_acta(carta_marina, fiscal_client):
    m1, m2, *_ = carta_marina
    AttachmentFactory(mesa=m1)
    AttachmentFactory(mesa=m2)
    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert response.status_code == 302
    assert response.url == reverse('mesa-cargar-resultados', args=(3, m1.numero))
    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert response.status_code == 302
    assert response.url == reverse('mesa-cargar-resultados', args=(3, m2.numero))