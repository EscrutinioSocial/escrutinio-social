import json
import pytest
from django.db.models import Sum
from django.urls import reverse
from elecciones.models import Categoria, Mesa, Distrito, Circuito, Seccion
from elecciones.views import ResultadosCategoria
from .factories import (
    CategoriaFactory,
    LugarVotacionFactory,
    SeccionFactory,
    FiscalFactory,
    OpcionFactory,
    CircuitoFactory,
    MesaFactory,
    AttachmentFactory,
    VotoMesaReportadoFactory,
)

@pytest.fixture()
def carta_marina(db):
    """
    1 distrito, 2 secciones con 2 circuitos y 2 mesas por circuito
    """
    s1, s2 = SeccionFactory.create_batch(2)
    c1, c2 = CircuitoFactory.create_batch(2, seccion=s1)
    c3, c4 = CircuitoFactory.create_batch(2, seccion=s2)
    return (
        MesaFactory(numero=1, lugar_votacion__circuito=c1, electores=100),
        MesaFactory(numero=2, lugar_votacion__circuito=c1, electores=100),
        MesaFactory(numero=3, lugar_votacion__circuito=c2, electores=120),
        MesaFactory(numero=4, lugar_votacion__circuito=c2, electores=120),
        MesaFactory(numero=5, lugar_votacion__circuito=c3, electores=90),
        MesaFactory(numero=6, lugar_votacion__circuito=c3, electores=90),
        MesaFactory(numero=7, lugar_votacion__circuito=c4, electores=90),
        MesaFactory(numero=8, lugar_votacion__circuito=c4, electores=90)
    )


@pytest.fixture()
def fiscal_client(db, admin_user, client):
    """A Django test client logged in as an admin user."""
    FiscalFactory(user=admin_user)
    client.login(username=admin_user.username, password='password')
    return client


@pytest.fixture()
def url_resultados(carta_marina):
    return reverse('resultados-categoria', args=[1])


def test_total_electores_en_categoria(carta_marina):
    # la sumatoria de todas las mesas de la categoria
    # nota: el factory de mesa indirectamente crea la categoria con id=1 que es actual()
    e2 = CategoriaFactory()
    m1, m2 = carta_marina[:2]
    m1.categoria_add(e2)
    m2.categoria_add(e2)

    assert Categoria.objects.first().electores == 800
    assert e2.electores == 200


def test_electores_filtro_mesa(url_resultados, fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=90)
    response = fiscal_client.get(url_resultados, {'mesa': mesa1.id})
    resultados = response.context['resultados']
    assert resultados['electores'] == 120
    assert b'<td title="Electores">120 </td>' in response.content


def test_electores_filtro_mesa_multiple_categoria(fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=120)      # mesa2 solo de la categoria 1
    e1 = CategoriaFactory()
    mesa1.categoria_add(e1)      # mesa 1 tambien está asociada a e1
    url = reverse('resultados-categoria', args=[e1.id])

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


def test_electores_filtro_distrito(url_resultados, fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=90, lugar_votacion__circuito__seccion__distrito__nombre='otro')
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
    categoria = Categoria.objects.first()
    # opciones a partido
    o1, o2, o3 = categoria.opciones.filter(partido__isnull=False)
    blanco = categoria.opciones.get(nombre='blanco')
    VotoMesaReportadoFactory(opcion=o1, carga__mesa=m1, carga__categoria=categoria, votos=20)
    VotoMesaReportadoFactory(opcion=o2, carga__mesa=m1, carga__categoria=categoria, votos=30)
    VotoMesaReportadoFactory(opcion=o3, carga__mesa=m1, carga__categoria=categoria, votos=40)

    # votaron 90/100 personas
    VotoMesaReportadoFactory(opcion=blanco, carga__mesa=m1, carga__categoria=categoria, votos=0)

    VotoMesaReportadoFactory(opcion=o1, carga__mesa=m3, carga__categoria=categoria, votos=30)
    VotoMesaReportadoFactory(opcion=o2, carga__mesa=m3, carga__categoria=categoria, votos=40)
    VotoMesaReportadoFactory(opcion=o3, carga__mesa=m3, carga__categoria=categoria, votos=50)

    # votaron 120/120 personas
    VotoMesaReportadoFactory(opcion=blanco, carga__mesa=m3, carga__categoria=categoria, votos=0)


    response = fiscal_client.get(url_resultados)
    resultados = response.context['resultados']
    positivos = resultados['tabla_positivos']

    assert resultados['porcentaje_mesas_escrutadas'] == '25.00'     # 2 de 8

    # se ordena de acuerdo al que va ganando
    assert list(positivos.keys()) == [o3.partido, o2.partido, o1.partido]

    total_positivos = resultados['positivos']

    assert total_positivos == 210  # 20 + 30 + 40 + 30 + 40 + 50

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


def test_resultados_proyectados(fiscal_client):
    url_resultados = reverse('resultados-categoria', args=[1])
    # se crean 3 secciones electorales
    s1, s2, s3 = SeccionFactory.create_batch(3)
    # s1 1000 votantes    # La matanza! :D
    # s2 400 votantes
    # s3 200 votantes

    # Se crean 8 mesas (5 en s1, 2 en s2 y 1 en s3). Todas tienen 200 electores
    ms1, ms2, ms3 = (
        MesaFactory.create_batch(5, lugar_votacion__circuito__seccion=s1, electores=200),
        MesaFactory.create_batch(2, lugar_votacion__circuito__seccion=s2, electores=200),
        MesaFactory.create_batch(1, lugar_votacion__circuito__seccion=s3, electores=200)
    )
    # ####################################################
    # El padron es de 1600 electores
    # ####################################################
    # La seccion 1 tiene a 1000, el 62.5% del padron
    # La seccion 2 tiene a  400, el 25  % del padron
    # La seccion 3 tiene a  200, el 12.5% del padron

    # tomo las primerar mesas de las secciones 1 y 3
    m1 = ms1[0]
    m3 = ms3[0]

    categoria = Categoria.objects.first()
    # opciones a partido
    o1, o2, o3 = categoria.opciones.filter(partido__isnull=False)
    blanco = categoria.opciones.get(nombre='blanco')

    # simulo que van entrandom resultados en las mesas 1 (la primera de la seccion 1) y 3 (la primera de la seccion 3)

    # Resultados de la mesa 1: 120 votos en la mesa 1 para el partido 1, 80 para el 2, 0 para el 3 y en blanco
    VotoMesaReportadoFactory(opcion=o1, carga__mesa=m1, carga__categoria=categoria, votos=120)      # 50% de los votos
    VotoMesaReportadoFactory(opcion=o2, carga__mesa=m1, carga__categoria=categoria, votos=80)       # 40%
    VotoMesaReportadoFactory(opcion=o3, carga__mesa=m1, carga__categoria=categoria, votos=0)
    VotoMesaReportadoFactory(opcion=blanco, carga__mesa=m1, carga__categoria=categoria, votos=0)

    # Resultados de la mesa 3: 79 votos al partido 1, 121 al partido 2 (cero los demas)
    VotoMesaReportadoFactory(opcion=o1, carga__mesa=m3, carga__categoria=categoria, votos=79)
    VotoMesaReportadoFactory(opcion=o2, carga__mesa=m3, carga__categoria=categoria, votos=121)
    VotoMesaReportadoFactory(opcion=o3, carga__mesa=m3, carga__categoria=categoria, votos=0)
    VotoMesaReportadoFactory(opcion=blanco, carga__mesa=m3, carga__categoria=categoria, votos=0)

    # ###################
    # Totales sin proyectar:
    # o1 (partido 1): 120 + 79 = 199 votos
    # o2 (partido 2): 80 + 121 = 201 votos
    # sin proyeccion va ganando o2 por 2 votos
    response = fiscal_client.get(url_resultados)
    positivos = response.context['resultados']['tabla_positivos']
    assert list(positivos.keys()) == [o2.partido, o1.partido, o3.partido]

    # cuentas
    assert positivos[o2.partido]['votos'] == 201
    assert positivos[o1.partido]['votos'] == 199
    assert positivos[o3.partido]['votos'] == 0
    assert positivos[o2.partido]['porcentajePositivos'] == '50.25'  # 201/400
    assert positivos[o1.partido]['porcentajePositivos'] == '49.75'  # 199/400
    # no hay proyeccion
    assert 'proyeccion' not in positivos[o1.partido]

    # cuando se proyecta, o1 gana porque va ganando en s1 que es la mas populosa
    response = fiscal_client.get(url_resultados + '?proyectado=✓')
    positivos = response.context['resultados']['tabla_positivos']
    assert list(positivos.keys()) == [o1.partido, o2.partido, o3.partido]

    # la contabilidad absoluta es la misma
    assert positivos[o2.partido]['votos'] == 201
    assert positivos[o1.partido]['votos'] == 199
    assert positivos[o3.partido]['votos'] == 0
    assert positivos[o2.partido]['porcentajePositivos'] == '50.25'
    assert positivos[o1.partido]['porcentajePositivos'] == '49.75'

    # PROYECCION:
    # la seccion 3 esta sobre representada por el momento (está al 100%)
    # en la seccion 1 todo se multiplica x 5 (tengo 1 de 5 mesas)
    # proyeccion de la seccion 1 es partido 1 = 120 * 5 (5=mesas totales/mesas actuales) = 600
    #                               partido 2 =  80 * 5 = 400
    # proyeccion p1 = 600 + 79 = 679
    # proyeccion p2 = 400 + 121 = 521
    # votos proyectados = 1200
    # p1 = 679 / 1200 = 56.58%
    # p3 = 521 / 1200 = 43.42%
    # OJO NO SE PUEDE PROYECTAR LA SECCION 2, no tiene ni una mesa
    # OJO, si el % de mesas es bajo la proyeccion puede ser ruidosa
    assert positivos[o1.partido]['proyeccion'] == '56.58'
    assert positivos[o2.partido]['proyeccion'] == '43.42'


def test_resultados_proyectados_simple(fiscal_client):
    s1, s2 = SeccionFactory.create_batch(2)
    o1, o2 = OpcionFactory.create_batch(2, es_contable=True)
    e1 = CategoriaFactory(opciones=[o1, o2])

    m1, *_ = MesaFactory.create_batch(3, categoria=[e1], lugar_votacion__circuito__seccion=s1, electores=200)
    m2 = MesaFactory(categoria=[e1], lugar_votacion__circuito__seccion=s2, electores=200)

    VotoMesaReportadoFactory(opcion=o1, carga__mesa=m1, carga__categoria=e1, votos=100)
    VotoMesaReportadoFactory(opcion=o2, carga__mesa=m1, carga__categoria=e1, votos=50)
    VotoMesaReportadoFactory(opcion=o1, carga__mesa=m2, carga__categoria=e1, votos=50)
    VotoMesaReportadoFactory(opcion=o2, carga__mesa=m2, carga__categoria=e1, votos=100)

    response = fiscal_client.get(reverse('resultados-categoria', args=[e1.id]) + '?proyectado=✓')

    positivos = response.context['resultados']['tabla_positivos']
    assert positivos[o1.partido]['porcentajePositivos'] == '50.00'
    assert positivos[o2.partido]['porcentajePositivos'] == '50.00'
    assert positivos[o1.partido]['proyeccion'] == '58.33'
    assert positivos[o2.partido]['proyeccion'] == '41.67'


def test_resultados_proyectados_usa_circuito(fiscal_client):
    # 2 secciones. 1 ponderada con 2 circuitos
    s1 = SeccionFactory(proyeccion_ponderada=True)
    c1, c2 = CircuitoFactory.create_batch(2, seccion=s1)
    c3 = CircuitoFactory()
    s2 = c2.seccion


    o1, o2 = OpcionFactory.create_batch(2, es_contable=True)
    e1 = CategoriaFactory(opciones=[o1, o2])

    ms1, ms2, ms3 = (
        MesaFactory.create_batch(4, categoria=[e1], lugar_votacion__circuito=c1, electores=200),
        MesaFactory.create_batch(2, categoria=[e1], lugar_votacion__circuito=c2, electores=200),
        MesaFactory.create_batch(2, categoria=[e1], lugar_votacion__circuito=c3, electores=200)
    )

    VotoMesaReportadoFactory(opcion=o1, carga__mesa=ms1[0], carga__categoria=e1, votos=70)
    VotoMesaReportadoFactory(opcion=o2, carga__mesa=ms1[0], carga__categoria=e1, votos=90)

    VotoMesaReportadoFactory(opcion=o1, carga__mesa=ms2[0], carga__categoria=e1, votos=90)
    VotoMesaReportadoFactory(opcion=o2, carga__mesa=ms2[0], carga__categoria=e1, votos=70)

    VotoMesaReportadoFactory(opcion=o1, carga__mesa=ms3[0], carga__categoria=e1, votos=80)
    VotoMesaReportadoFactory(opcion=o2, carga__mesa=ms3[0], carga__categoria=e1, votos=80)

    response = fiscal_client.get(reverse('resultados-categoria', args=[e1.id]) + '?proyectado=✓')
    positivos = response.context['resultados']['tabla_positivos']

    assert positivos[o1.partido]['porcentajePositivos'] == '50.00'
    assert positivos[o2.partido]['porcentajePositivos'] == '50.00'
    assert positivos[o2.partido]['proyeccion'] == '51.56'
    assert positivos[o1.partido]['proyeccion'] == '48.44'

    s1.proyeccion_ponderada = False
    s1.save()

    # proyeccion sin ponderar circuitos
    response = fiscal_client.get(reverse('resultados-categoria', args=[e1.id]) + '?proyectado=✓')
    positivos = response.context['resultados']['tabla_positivos']

    assert positivos[o1.partido]['porcentajePositivos'] == '50.00'
    assert positivos[o2.partido]['porcentajePositivos'] == '50.00'
    assert positivos[o2.partido]['proyeccion'] == '50.00'
    assert positivos[o1.partido]['proyeccion'] == '50.00'



def test_mesa_orden(carta_marina):
    m1, m2, *_ = carta_marina
    AttachmentFactory(mesa=m1)
    assert m1.orden_de_carga == 1
    assert m2.orden_de_carga == 0
    AttachmentFactory(mesa=m2)
    # assert m2.orden_de_carga == 2 porque? Da error, ambas tienen igual prioridad.


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



def test_resultados_no_positivos(fiscal_client):
    o1, o2 = OpcionFactory.create_batch(2, es_contable=True)
    o3 = OpcionFactory(nombre='blanco', partido=None, es_contable=False)
    e1 = CategoriaFactory(opciones=[o1, o2, o3])

    m1 = MesaFactory(categoria=[e1], electores=200)

    VotoMesaReportadoFactory(opcion=o1, carga__mesa=m1, carga__categoria=e1, votos=50)
    VotoMesaReportadoFactory(opcion=o2, carga__mesa=m1, carga__categoria=e1, votos=40)
    VotoMesaReportadoFactory(opcion=o3, carga__mesa=m1, carga__categoria=e1, votos=10)

    response = fiscal_client.get(reverse('resultados-categoria', args=[e1.id]))
    assert o3.nombre in response.content.decode('utf8')
    no_positivos = response.context['resultados']['tabla_no_positivos']
    assert no_positivos['blanco'] == 10
    assert no_positivos['Positivos']['votos'] == 90


def test_resultados_excluye_metadata(fiscal_client):


    s1, s2 = SeccionFactory.create_batch(2)
    o1, o2 = OpcionFactory.create_batch(2, es_contable=True)
    o3 = OpcionFactory(partido=None, es_contable=False)
    o4 = OpcionFactory(nombre='TOTAL', partido=None, es_contable=False, es_metadata=True)
    e1 = CategoriaFactory(opciones=[o1, o2, o3, o4])

    m1, *_ = MesaFactory.create_batch(3, categoria=[e1], lugar_votacion__circuito__seccion=s1, electores=200)
    m2 = MesaFactory(categoria=[e1], lugar_votacion__circuito__seccion=s2, electores=200)

    VotoMesaReportadoFactory(opcion=o1, carga__mesa=m1, carga__categoria=e1, votos=100)
    VotoMesaReportadoFactory(opcion=o2, carga__mesa=m1, carga__categoria=e1, votos=50)
    VotoMesaReportadoFactory(opcion=o3, carga__mesa=m1, carga__categoria=e1, votos=10)
    VotoMesaReportadoFactory(opcion=o4, carga__mesa=m1, carga__categoria=e1, votos=160)

    VotoMesaReportadoFactory(opcion=o1, carga__mesa=m2, carga__categoria=e1, votos=50)
    VotoMesaReportadoFactory(opcion=o2, carga__mesa=m2, carga__categoria=e1, votos=100)
    VotoMesaReportadoFactory(opcion=o3, carga__mesa=m2, carga__categoria=e1, votos=10)
    VotoMesaReportadoFactory(opcion=o4, carga__mesa=m2, carga__categoria=e1, votos=160)

    response = fiscal_client.get(reverse('resultados-categoria', args=[e1.id]) + '?proyectado=✓')

    positivos = response.context['resultados']['tabla_positivos']
    no_positivos = response.context['resultados']['tabla_no_positivos']

    assert positivos[o1.partido]['votos'] == 150
    assert positivos[o2.partido]['votos'] == 150
    assert no_positivos['Positivos']['votos'] == 300

    assert positivos[o1.partido]['porcentajePositivos'] == '50.00'
    assert positivos[o2.partido]['porcentajePositivos'] == '50.00'
    assert positivos[o1.partido]['proyeccion'] == '58.33'
    assert positivos[o2.partido]['proyeccion'] == '41.67'

    assert no_positivos[o3.nombre] == 20
    assert list(no_positivos.keys()) == [o3.nombre, 'Positivos']


def test_actualizar_electores(carta_marina):
    """
    prueba :func:`elecciones.models.actualizar_electores`
    """
    m1 = carta_marina[0]
    c1 = m1.lugar_votacion.circuito
    assert c1.electores == 100 * 2
    s1 = c1.seccion
    assert s1.electores == 100 * 2 + 120 * 2
    d = s1.distrito
    d.refresh_from_db()
    assert d.electores == 100 * 2 + 120 * 2 + 90 * 4