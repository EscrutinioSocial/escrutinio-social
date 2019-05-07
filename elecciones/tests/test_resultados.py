import json
import pytest
from django.db.models import Sum
from django.urls import reverse
from elecciones.models import Eleccion, Mesa
from elecciones.views import ResultadosEleccion, TOTAL, POSITIVOS
from .factories import (
    EleccionFactory,
    LugarVotacionFactory,
    SeccionFactory,
    FiscalFactory,
    CircuitoFactory,
    MesaFactory,
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
def fiscal_client(db, admin_user, client):
    """A Django test client logged in as an admin user."""
    FiscalFactory(user=admin_user)
    client.login(username=admin_user.username, password='password')
    return client


@pytest.fixture()
def url_resultados(carta_marina):
    return reverse('resultados-eleccion', args=[1])


def test_total_electores_en_eleccion(carta_marina):
    # la sumatoria de todas las mesas de la eleccion
    # nota: el factory de mesa indirectamente crea la eleccion con id=1 que es actual()
    e2 = EleccionFactory()
    m1, m2 = carta_marina[:2]
    m1.eleccion.add(e2)
    m2.eleccion.add(e2)

    assert Eleccion.objects.get(id=1).electores == 800
    assert e2.electores == 200


def test_electores_filtro_mesa(url_resultados, fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=90)
    response = fiscal_client.get(url_resultados, {'mesa': mesa1.id})
    resultados = response.context['resultados']
    assert resultados['electores'] == 120
    assert b'<td title="Electores">120 </td>' in response.content


def test_electores_filtro_mesa_multiple_eleccion(fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=120)      # mesa2 solo de la eleccion 1
    e1 = EleccionFactory()
    mesa1.eleccion.add(e1)      # mesa 1 tambien está asociada a e1
    url = reverse('resultados-eleccion', args=[e1.id])

    response = fiscal_client.get(url, {'mesa': mesa1.id})
    resultados = response.context['resultados']
    assert resultados['electores'] == 120
    assert b'<td title="Electores">120 </td>' in response.content



def test_electores_filtro_escuela(url_resultados, fiscal_client):
    e = LugarVotacionFactory()
    MesaFactory(electores=120, lugar_votacion=e)
    MesaFactory(electores=80, lugar_votacion=e)
    MesaFactory(electores=90)
    response = fiscal_client.get(url_resultados, {'lugarvotacion': e.id})
    resultados = response.context['resultados']
    assert resultados['electores'] == 200
    assert b'<td title="Electores">200 </td>' in response.content


def test_electores_filtro_circuito(url_resultados, fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=90)
    response = fiscal_client.get(url_resultados, {'circuito': mesa1.lugar_votacion.circuito.id})
    resultados = response.context['resultados']
    assert resultados['electores'] == 120
    assert b'<td title="Electores">120 </td>' in response.content


def test_electores_filtro_seccion(url_resultados, fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=90)
    response = fiscal_client.get(url_resultados, {'seccion': mesa1.lugar_votacion.circuito.seccion.id})
    resultados = response.context['resultados']
    assert resultados['electores'] == 120
    assert b'<td title="Electores">120 </td>' in response.content


def test_electores_sin_filtro(url_resultados, fiscal_client):
    response = fiscal_client.get(url_resultados)
    resultados = response.context['resultados']
    assert resultados['electores'] == 800
    assert b'<td title="Electores">800 </td>' in response.content


def test_resultados_parciales(carta_marina, url_resultados, fiscal_client):
    # resultados para mesa 1
    m1, _, m3, *_ = carta_marina
    eleccion = Eleccion.objects.get(id=1)
    # opciones a partido
    o1, o2, o3 = eleccion.opciones.filter(partido__isnull=False)
    total = eleccion.opciones.get(nombre=TOTAL)
    VotoMesaReportadoFactory(opcion=o1, mesa=m1, eleccion=eleccion, votos=20)
    VotoMesaReportadoFactory(opcion=o2, mesa=m1, eleccion=eleccion, votos=30)
    VotoMesaReportadoFactory(opcion=o3, mesa=m1, eleccion=eleccion, votos=40)

    # votaron 90/100 personas
    VotoMesaReportadoFactory(opcion=total, mesa=m1, eleccion=eleccion, votos=90)

    VotoMesaReportadoFactory(opcion=o1, mesa=m3, eleccion=eleccion, votos=30)
    VotoMesaReportadoFactory(opcion=o2, mesa=m3, eleccion=eleccion, votos=40)
    VotoMesaReportadoFactory(opcion=o3, mesa=m3, eleccion=eleccion, votos=50)

    # votaron 120/120 personas
    VotoMesaReportadoFactory(opcion=total, mesa=m3, eleccion=eleccion, votos=120)

    response = fiscal_client.get(url_resultados)
    resultados = response.context['resultados']
    positivos = resultados['tabla_positivos']

    # se ordena de acuerdo al que va ganando
    assert list(positivos.keys()) == [o3.partido, o2.partido, o1.partido]

    total_positivos = resultados['positivos']

    assert total_positivos == 210 == 20 + 30 + 40 + 30 + 40 + 50

    # cuentas
    assert positivos[o3.partido]['votos'] == 40 + 50
    assert positivos[o3.partido]['porcentajePositivos'] == '42.86' # (40 + 50) / total_positivos
    assert positivos[o2.partido]['votos'] == 30 + 40
    assert positivos[o2.partido]['porcentajePositivos'] == '33.33' #  (30 + 40) / total_positivos
    assert positivos[o1.partido]['votos'] == 20 + 30
    assert positivos[o1.partido]['porcentajePositivos'] == '23.81' # (20 + 30) / total_positivos

    # todos los positivos suman 100
    assert sum(float(v['porcentajePositivos']) for v in positivos.values()) == 100.0

    content = response.content.decode('utf8')
    assert f'<td id="votos_{o1.partido.id}"> 50</td>' in content
    assert f'<td id="votos_{o2.partido.id}"> 70</td>' in content
    assert f'<td id="votos_{o3.partido.id}"> 90</td>' in content

    assert resultados['votantes'] == 210
    assert resultados['electores'] == 800


def test_mesa_orden(carta_marina):
    m1, m2, *_ = carta_marina
    AttachmentFactory(mesa=m1)
    assert m1.orden_de_carga == 1
    assert m2.orden_de_carga == 0
    AttachmentFactory(mesa=m2)
    assert m2.orden_de_carga == 2


def test_orden_para_circuito(db):
    c1 = CircuitoFactory()  # sin mesas
    assert c1.proximo_orden_de_carga() == 1
    MesaFactory(lugar_votacion__circuito=c1)
    MesaFactory(lugar_votacion__circuito=c1, orden_de_carga=3)
    assert c1.proximo_orden_de_carga() == 4



def test_elegir_acta(carta_marina, fiscal_client):
    m1, m2, *_ = carta_marina
    AttachmentFactory(mesa=m1)
    AttachmentFactory(mesa=m2)
    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert response.status_code == 302
    assert response.url == reverse('mesa-cargar-resultados', args=(1, m1.numero))
    response = fiscal_client.get(reverse('elegir-acta-a-cargar'))
    assert response.status_code == 302
    assert response.url == reverse('mesa-cargar-resultados', args=(1, m2.numero))