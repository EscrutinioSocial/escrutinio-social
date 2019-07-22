import pytest
from django.urls import reverse
from django.contrib.auth.models import Group
from elecciones.models import (Categoria, MesaCategoria, Carga)
from .factories import (
    UserFactory,
    CategoriaFactory,
    LugarVotacionFactory,
    SeccionFactory,
    FiscalFactory,
    OpcionFactory,
    CircuitoFactory,
    MesaFactory,
    MesaCategoriaFactory,
    IdentificacionFactory,
    VotoMesaReportadoFactory,
    CargaFactory,
)
from adjuntos.models import Identificacion
from adjuntos.consolidacion import consumir_novedades_identificacion
from .test_models import consumir_novedades_y_actualizar_objetos


@pytest.fixture()
def carta_marina(db):
    """
    1 distrito, 2 secciones con 2 circuitos y 2 mesas por circuito
    """
    s1, s2 = SeccionFactory.create_batch(2)
    c1, c2 = CircuitoFactory.create_batch(2, seccion=s1)
    c3, c4 = CircuitoFactory.create_batch(2, seccion=s2)
    return (
        MesaFactory(numero=1, lugar_votacion__circuito=c1,
                    electores=100), MesaFactory(numero=2, lugar_votacion__circuito=c1, electores=100),
        MesaFactory(numero=3, lugar_votacion__circuito=c2,
                    electores=120), MesaFactory(numero=4, lugar_votacion__circuito=c2, electores=120),
        MesaFactory(numero=5, lugar_votacion__circuito=c3,
                    electores=90), MesaFactory(numero=6, lugar_votacion__circuito=c3, electores=90),
        MesaFactory(numero=7, lugar_votacion__circuito=c4,
                    electores=90), MesaFactory(numero=8, lugar_votacion__circuito=c4, electores=90)
    )


@pytest.fixture()
def setup_groups(db, admin_user):
    groups = [
        'validadores', 'unidades basicas', 'visualizadores', 'supervisores', 'fiscales con acceso al bot'
    ]
    for nombre in groups:
        g = Group.objects.create(name=nombre)
        admin_user.groups.add(g)


@pytest.fixture()
def fiscal_client(db, admin_user, setup_groups, client):
    """A Django test client logged in as an admin user."""
    FiscalFactory(user=admin_user)
    client.login(username=admin_user.username, password='password')
    return client


@pytest.fixture()
def url_resultados(carta_marina):
    c = CategoriaFactory(nombre='default')
    return reverse('resultados-categoria', args=[c.id])


def test_total_electores_en_categoria(carta_marina):
    # la sumatoria de todas las mesas de la categoria
    # implicitamente está creada la categoria default que tiene todo el padron
    assert Categoria.objects.get().electores == 800
    e2 = CategoriaFactory()
    m1, m2 = carta_marina[:2]
    m1.categoria_add(e2)
    m2.categoria_add(e2)

    assert e2.electores == 200


def test_electores_filtro_mesa(url_resultados, fiscal_client):
    mesa1 = MesaFactory(electores=120)
    response = fiscal_client.get(url_resultados, {'mesa': mesa1.id})
    resultados = response.context['resultados']
    assert resultados.electores() == 120
    assert b'<td title="Electores">120 </td>' in response.content


def test_electores_filtro_mesa_multiple_categoria(fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=120)  # mesa2 solo de la categoria 1
    e1 = CategoriaFactory()
    mesa1.categoria_add(e1)  # mesa 1 tambien está asociada a e1
    url = reverse('resultados-categoria', args=[e1.id])

    response = fiscal_client.get(url, {'mesa': mesa1.id})
    resultados = response.context['resultados']
    assert resultados.electores() == 120
    assert b'<td title="Electores">120 </td>' in response.content


def test_electores_filtro_escuela(url_resultados, fiscal_client):
    e = LugarVotacionFactory()
    MesaFactory(electores=120, lugar_votacion=e)
    MesaFactory(electores=80, lugar_votacion=e)
    MesaFactory(electores=90)
    response = fiscal_client.get(url_resultados, {'lugar_de_votacion': e.id})
    resultados = response.context['resultados']
    assert resultados.electores() == 200
    assert b'<td title="Electores">200 </td>' in response.content


def test_electores_filtro_circuito(url_resultados, fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=90)
    response = fiscal_client.get(url_resultados, {'circuito': mesa1.lugar_votacion.circuito.id})
    resultados = response.context['resultados']
    assert resultados.electores() == 120
    assert b'<td title="Electores">120 </td>' in response.content


def test_electores_filtro_seccion(url_resultados, fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=90)
    response = fiscal_client.get(url_resultados, {'seccion': mesa1.lugar_votacion.circuito.seccion.id})
    resultados = response.context['resultados']
    assert resultados.electores() == 120
    assert b'<td title="Electores">120 </td>' in response.content


def test_electores_filtro_distrito(url_resultados, fiscal_client):
    mesa1 = MesaFactory(electores=120)
    m2 = MesaFactory(electores=90, lugar_votacion__circuito__seccion__distrito__nombre='otro')
    response = fiscal_client.get(
        url_resultados, {'distrito': m2.lugar_votacion.circuito.seccion.distrito.id}
    )
    resultados = response.context['resultados']
    assert resultados.electores() == 90
    assert b'<td title="Electores">90 </td>' in response.content


def test_electores_sin_filtro(url_resultados, fiscal_client):
    response = fiscal_client.get(url_resultados)
    resultados = response.context['resultados']
    assert resultados.electores() == 800
    assert b'<td title="Electores">800 </td>' in response.content


def test_resultados_parciales(carta_marina, url_resultados, fiscal_client):
    # resultados para mesa 1
    m1, _, m3, *_ = carta_marina
    categoria = m1.categorias.get()  # sólo default
    # opciones a partido
    o1, o2, o3, o4 = categoria.opciones.filter(partido__isnull=False)
    # la opción 4 pasa a ser del mismo partido que la 1
    o4.partido = o1.partido
    o4.save()
    blanco = categoria.opciones.get(nombre='blanco')
    mc1 = MesaCategoria.objects.get(mesa=m1, categoria=categoria)
    mc3 = MesaCategoria.objects.get(mesa=m3, categoria=categoria)
    c1 = CargaFactory(mesa_categoria=mc1, tipo=Carga.TIPOS.parcial)
    c2 = CargaFactory(mesa_categoria=mc3, tipo=Carga.TIPOS.parcial)
    consumir_novedades_y_actualizar_objetos([m1, m3])

    VotoMesaReportadoFactory(carga=c1, opcion=o1, votos=20)
    VotoMesaReportadoFactory(carga=c1, opcion=o2, votos=30)
    VotoMesaReportadoFactory(carga=c1, opcion=o3, votos=40)
    VotoMesaReportadoFactory(carga=c1, opcion=o4, votos=5)

    # votaron 95/100 personas
    VotoMesaReportadoFactory(carga=c1, opcion=blanco, votos=0)

    VotoMesaReportadoFactory(carga=c2, opcion=o1, votos=10)
    VotoMesaReportadoFactory(carga=c2, opcion=o2, votos=40)
    VotoMesaReportadoFactory(carga=c2, opcion=o3, votos=50)
    VotoMesaReportadoFactory(carga=c2, opcion=o4, votos=20)

    # votaron 120/120 personas
    VotoMesaReportadoFactory(carga=c2, opcion=blanco, votos=0)
    c1.actualizar_firma()
    c2.actualizar_firma()
    assert c1.es_testigo.exists()
    assert c2.es_testigo.exists()

    response = fiscal_client.get(url_resultados)
    resultados = response.context['resultados']
    positivos = resultados.tabla_positivos()

    assert resultados.porcentaje_mesas_escrutadas() == '25.00'  # 2 de 8

    # se ordena de acuerdo al que va ganando
    assert list(positivos.keys()) == [o3.partido, o2.partido, o1.partido]

    total_positivos = resultados.positivos()

    assert total_positivos == 215  # 20 + 5 + 30 + 40 + 20 + 10 + 40 + 50

    # cuentas
    assert positivos[o3.partido]['votos'] == 40 + 50
    assert positivos[o3.partido]['porcentaje_positivos'] == '41.86'  # (40 + 50) / total_positivos
    assert positivos[o2.partido]['votos'] == 30 + 40
    assert positivos[o2.partido]['porcentaje_positivos'] == '32.56'  # (30 + 40) / total_positivos
    assert positivos[o1.partido]['votos'] == 10 + 20 + 20 + 5
    assert positivos[o1.partido]['porcentaje_positivos'] == '25.58'  # (20 + 5 + 10 + 20) / total_positivos

    # todos los positivos suman 100
    assert sum(float(v['porcentaje_positivos']) for v in positivos.values()) == 100.0

    # votos de partido 1 son iguales a los de o1 + o4
    assert positivos[o1.partido]['votos'] == sum(
        x['votos'] for x in positivos[o4.partido]['detalle'].values()
    )

    content = response.content.decode('utf8')

    assert f'<td id="votos_{o1.partido.id}" class="dato">55</td>' in content
    assert f'<td id="votos_{o2.partido.id}" class="dato">70</td>' in content
    assert f'<td id="votos_{o3.partido.id}" class="dato">90</td>' in content

    assert resultados.votantes() == 215
    assert resultados.electores() == 800


@pytest.mark.skip(reason="proyecciones sera re-escrito")
def test_resultados_proyectados(fiscal_client, url_resultados):
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

    categoria = Categoria.objects.get()
    # opciones a partido
    o1, o2, o3, o4 = categoria.opciones.filter(partido__isnull=False)
    blanco = categoria.opciones.get(nombre='blanco')

    # simulo que van entrandom resultados en las mesas 1 (la primera de la seccion 1) y 3 (la primera de la seccion 3)
    # Resultados de la mesa 1: 120 votos en la mesa 1 para el partido 1, 80 para el 2, 0 para el 3 y en blanco
    c1 = CargaFactory(mesa_categoria__mesa=m1, tipo=Carga.TIPOS.parcial, mesa_categoria__categoria=categoria)
    consumir_novedades_y_actualizar_objetos([m1])

    VotoMesaReportadoFactory(opcion=o1, carga=c1, votos=120)  # 50% de los votos
    VotoMesaReportadoFactory(opcion=o2, carga=c1, votos=80)  # 40%
    VotoMesaReportadoFactory(opcion=o3, carga=c1, votos=0)
    VotoMesaReportadoFactory(opcion=blanco, carga=c1, votos=0)

    # Resultados de la mesa 3: 79 votos al partido 1, 121 al partido 2 (cero los demas)
    c2 = CargaFactory(mesa_categoria__mesa=m3, tipo=Carga.TIPOS.parcial, mesa_categoria__categoria=categoria)
    consumir_novedades_y_actualizar_objetos([m1, m3])
    VotoMesaReportadoFactory(opcion=o1, carga=c2, votos=79)
    VotoMesaReportadoFactory(opcion=o2, carga=c2, votos=121)
    VotoMesaReportadoFactory(opcion=o3, carga=c2, votos=0)
    VotoMesaReportadoFactory(opcion=blanco, carga=c2, votos=0)
    c1.actualizar_firma()
    c2.actualizar_firma()

    # ###################
    # Totales sin proyectar:
    # o1 (partido 1): 120 + 79 = 199 votos
    # o2 (partido 2): 80 + 121 = 201 votos
    # sin proyeccion va ganando o2 por 2 votos
    response = fiscal_client.get(url_resultados)
    positivos = response.context['resultados'].tabla_positivos()
    assert list(positivos.keys()) == [o2.partido, o1.partido, o3.partido]

    # cuentas
    assert positivos[o2.partido]['votos'] == 201
    assert positivos[o1.partido]['votos'] == 199
    assert positivos[o3.partido]['votos'] == 0
    assert positivos[o2.partido]['porcentaje_positivos'] == '50.25'  # 201/400
    assert positivos[o1.partido]['porcentaje_positivos'] == '49.75'  # 199/400
    # no hay proyeccion
    assert 'proyeccion' not in positivos[o1.partido]

    # cuando se proyecta, o1 gana porque va ganando en s1 que es la mas populosa
    response = fiscal_client.get(url_resultados + '?tipodesumarizacion=2')
    positivos = response.context['resultados'].tabla_positivos()
    assert list(positivos.keys()) == [o1.partido, o2.partido, o3.partido]

    # la contabilidad absoluta es la misma
    assert positivos[o2.partido]['votos'] == 201
    assert positivos[o1.partido]['votos'] == 199
    assert positivos[o3.partido]['votos'] == 0
    assert positivos[o2.partido]['porcentaje_positivos'] == '50.25'
    assert positivos[o1.partido]['porcentaje_positivos'] == '49.75'

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


@pytest.mark.skip(reason="proyecciones sera re-escrito")
def test_resultados_proyectados_simple(fiscal_client):
    s1, s2 = SeccionFactory.create_batch(2)
    o1, o2 = OpcionFactory.create_batch(2)
    e1 = CategoriaFactory(opciones=[o1, o2])

    m1, *_ = MesaFactory.create_batch(
        3, categorias=[e1], lugar_votacion__circuito__seccion=s1, electores=200
    )
    m2 = MesaFactory(categorias=[e1], lugar_votacion__circuito__seccion=s2, electores=200)

    c1 = CargaFactory(mesa_categoria__mesa=m1, tipo=Carga.TIPOS.parcial, mesa_categoria__categoria=e1)
    VotoMesaReportadoFactory(opcion=o1, carga=c1, votos=100)
    VotoMesaReportadoFactory(opcion=o2, carga=c1, votos=50)
    c2 = CargaFactory(mesa_categoria__mesa=m2, tipo=Carga.TIPOS.parcial, mesa_categoria__categoria=e1)
    VotoMesaReportadoFactory(opcion=o1, carga=c2, votos=50)
    VotoMesaReportadoFactory(opcion=o2, carga=c2, votos=100)
    c1.actualizar_firma()
    c2.actualizar_firma()
    consumir_novedades_y_actualizar_objetos([m1, m2])

    response = fiscal_client.get(reverse('resultados-categoria', args=[e1.id]) + '?tipodesumarizacion=2')

    positivos = response.context['resultados'].tabla_positivos()
    assert positivos[o1.partido]['porcentaje_positivos'] == '50.00'
    assert positivos[o2.partido]['porcentaje_positivos'] == '50.00'
    assert positivos[o1.partido]['proyeccion'] == '58.33'
    assert positivos[o2.partido]['proyeccion'] == '41.67'


@pytest.mark.skip(reason="proyecciones sera re-escrito")
def test_resultados_proyectados_usa_circuito(fiscal_client):
    # 2 secciones. 1 ponderada con 2 circuitos
    s1 = SeccionFactory(proyeccion_ponderada=True)
    c1, c2 = CircuitoFactory.create_batch(2, seccion=s1)
    c3 = CircuitoFactory()

    o1, o2 = OpcionFactory.create_batch(2)
    e1 = CategoriaFactory(opciones=[o1, o2])

    ms1, ms2, ms3 = (
        MesaFactory.create_batch(4, categorias=[e1], lugar_votacion__circuito=c1, electores=200),
        MesaFactory.create_batch(2, categorias=[e1], lugar_votacion__circuito=c2, electores=200),
        MesaFactory.create_batch(2, categorias=[e1], lugar_votacion__circuito=c3, electores=200)
    )
    c1 = CargaFactory(mesa_categoria__mesa=ms1[0], tipo=Carga.TIPOS.parcial, mesa_categoria__categoria=e1)
    VotoMesaReportadoFactory(opcion=o1, carga=c1, votos=70)
    VotoMesaReportadoFactory(opcion=o2, carga=c1, votos=90)

    c2 = CargaFactory(mesa_categoria__mesa=ms2[0], tipo=Carga.TIPOS.parcial, mesa_categoria__categoria=e1)
    VotoMesaReportadoFactory(opcion=o1, carga=c2, votos=90)
    VotoMesaReportadoFactory(opcion=o2, carga=c2, votos=70)

    c3 = CargaFactory(mesa_categoria__mesa=ms3[0], tipo=Carga.TIPOS.parcial, mesa_categoria__categoria=e1)
    VotoMesaReportadoFactory(opcion=o1, carga=c3, votos=80)
    VotoMesaReportadoFactory(opcion=o2, carga=c3, votos=80)
    c1.actualizar_firma()
    c2.actualizar_firma()
    c3.actualizar_firma()

    consumir_novedades_y_actualizar_objetos()

    response = fiscal_client.get(reverse('resultados-categoria', args=[e1.id]) + '?tipodesumarizacion=2')
    positivos = response.context['resultados'].tabla_positivos()

    assert positivos[o1.partido]['porcentaje_positivos'] == '50.00'
    assert positivos[o2.partido]['porcentaje_positivos'] == '50.00'
    assert positivos[o2.partido]['proyeccion'] == '51.56'
    assert positivos[o1.partido]['proyeccion'] == '48.44'

    s1.proyeccion_ponderada = False
    s1.save()

    # proyeccion sin ponderar circuitos
    response = fiscal_client.get(reverse('resultados-categoria', args=[e1.id]) + '?tipodesumarizacion=2')
    positivos = response.context['resultados'].tabla_positivos()

    assert positivos[o1.partido]['porcentaje_positivos'] == '50.00'
    assert positivos[o2.partido]['porcentaje_positivos'] == '50.00'
    assert positivos[o2.partido]['proyeccion'] == '50.00'
    assert positivos[o1.partido]['proyeccion'] == '50.00'


def test_solo_total_confirmado_y_sin_confirmar(carta_marina, url_resultados, fiscal_client):
    m1, _, m3, *_ = carta_marina
    categoria = m1.categorias.get()
    # opciones a partido
    blanco = categoria.opciones.get(nombre='blanco')

    c1 = CargaFactory(mesa_categoria__mesa=m1, mesa_categoria__categoria=categoria, tipo=Carga.TIPOS.total)
    VotoMesaReportadoFactory(carga=c1, opcion=blanco, votos=20)
    c1.actualizar_firma()
    mc = c1.mesa_categoria
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.carga_testigo == c1
    assert mc.status == MesaCategoria.STATUS.total_sin_consolidar

    response = fiscal_client.get(reverse('resultados-totales-sin-confirmar', args=[categoria.id]))
    resultados = response.context['resultados']
    assert resultados.tabla_no_positivos()['blanco']['votos'] == 20
    assert resultados.total_mesas_escrutadas() == 1

    response = fiscal_client.get(reverse('resultados-totales-confirmados', args=[categoria.id]))
    resultados = response.context['resultados']
    assert 'blanco' not in resultados.tabla_no_positivos()
    assert resultados.total_mesas_escrutadas() == 0

    c2 = CargaFactory(mesa_categoria__mesa=m1, mesa_categoria__categoria=categoria, tipo=Carga.TIPOS.total)
    VotoMesaReportadoFactory(carga=c2, opcion=blanco, votos=20)
    c2.actualizar_firma()

    consumir_novedades_y_actualizar_objetos([mc])
    assert mc == c2.mesa_categoria
    # la carga testigo sigue siendo la primera coincidentes
    assert mc.carga_testigo == c1
    assert mc.status == MesaCategoria.STATUS.total_consolidada_dc

    response = fiscal_client.get(reverse('resultados-totales-sin-confirmar', args=[categoria.id]))
    resultados = response.context['resultados']
    assert resultados.tabla_no_positivos()['blanco']['votos'] == 20
    assert resultados.total_mesas_escrutadas() == 1

    response = fiscal_client.get(reverse('resultados-totales-confirmados', args=[categoria.id]))
    resultados = response.context['resultados']
    assert resultados.tabla_no_positivos()['blanco']['votos'] == 20
    assert resultados.total_mesas_escrutadas() == 1


def test_parcial_confirmado(carta_marina, url_resultados, fiscal_client):
    m1, _, m3, *_ = carta_marina
    categoria = m1.categorias.get()
    # opciones a partido
    blanco = categoria.opciones.get(nombre='blanco')

    c1 = CargaFactory(tipo=Carga.TIPOS.parcial, mesa_categoria__mesa=m1, mesa_categoria__categoria=categoria)
    VotoMesaReportadoFactory(carga=c1, opcion=blanco, votos=20)
    c1.actualizar_firma()
    consumir_novedades_y_actualizar_objetos()

    # TODO dependiendo de lo que se quiera la url podria ser algo como por ejemplo:
    # response = fiscal_client.get(reverse('resultados-categoria', args=[categoria.id]) + '?tipoDeAgregacion=solo_consolidados&opcionaConsiderar=prioritarias')
    response = fiscal_client.get(reverse('resultados-parciales-confirmados', args=[categoria.id]))

    resultados = response.context['resultados']
    # la carga está en status sin_confirmar
    assert 'blanco' not in resultados.tabla_no_positivos()
    assert resultados.total_mesas_escrutadas() == 0

    c2 = CargaFactory(tipo=Carga.TIPOS.parcial, mesa_categoria__mesa=m1, mesa_categoria__categoria=categoria)
    VotoMesaReportadoFactory(carga=c2, opcion=blanco, votos=20)
    c2.actualizar_firma()
    mc = c1.mesa_categoria
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc == c2.mesa_categoria
    assert mc.carga_testigo in [c1, c2]
    assert mc.status == MesaCategoria.STATUS.parcial_consolidada_dc

    response = fiscal_client.get(reverse('resultados-parciales-confirmados', args=[categoria.id]))
    resultados = response.context['resultados']
    # Como tenemos dos cargas confirmadas, se modifica el resultado.
    assert resultados.tabla_no_positivos()['blanco']['votos'] == 20
    assert resultados.total_mesas_escrutadas() == 1

    c3 = CargaFactory(tipo=Carga.TIPOS.parcial, mesa_categoria__mesa=m3, mesa_categoria__categoria=categoria)
    VotoMesaReportadoFactory(carga=c3, opcion=blanco, votos=10)
    c3.actualizar_firma()
    consumir_novedades_y_actualizar_objetos([mc])
    response = fiscal_client.get(reverse('resultados-parciales-confirmados', args=[categoria.id]))
    resultados = response.context['resultados']
    # c3 no está confirmada, no varía el resultado.
    assert resultados.tabla_no_positivos()['blanco']['votos'] == 20
    assert resultados.total_mesas_escrutadas() == 1

    c4 = CargaFactory(tipo=Carga.TIPOS.parcial, mesa_categoria__mesa=m3, mesa_categoria__categoria=categoria)
    VotoMesaReportadoFactory(carga=c4, opcion=blanco, votos=10)
    c4.actualizar_firma()
    consumir_novedades_y_actualizar_objetos([mc])

    response = fiscal_client.get(reverse('resultados-parciales-confirmados', args=[categoria.id]))
    resultados = response.context['resultados']
    # Ahora sí varía.
    assert resultados.tabla_no_positivos()['blanco']['votos'] == 30
    assert resultados.total_mesas_escrutadas() == 2


def test_siguiente_accion_cargar_acta(fiscal_client):
    c = CategoriaFactory(nombre='default')
    m1 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    m2 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    mc1 = MesaCategoriaFactory(mesa=m1, categoria=c)
    mc2 = MesaCategoriaFactory(mesa=m2, categoria=c)
    consumir_novedades_identificacion()
    response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.status_code == 302
    assert response.url == reverse('carga-total', args=(mc1.id, ))
    response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.status_code == 302
    assert response.url == reverse('carga-total', args=(mc2.id, ))


def test_resultados_no_positivos(fiscal_client):
    o1, o2 = OpcionFactory.create_batch(2)
    o3 = OpcionFactory(nombre='blanco', partido=None, tipo='no_positivo')
    e1 = CategoriaFactory(opciones=[o1, o2, o3])

    m1 = MesaFactory(categorias=[e1], electores=200)
    c1 = CargaFactory(mesa_categoria__categoria=e1, mesa_categoria__mesa=m1, tipo=Carga.TIPOS.parcial)
    VotoMesaReportadoFactory(opcion=o1, carga=c1, votos=50)
    VotoMesaReportadoFactory(opcion=o2, carga=c1, votos=40)
    VotoMesaReportadoFactory(opcion=o3, carga=c1, votos=10)
    c1.actualizar_firma()
    consumir_novedades_y_actualizar_objetos()

    response = fiscal_client.get(reverse('resultados-categoria', args=[e1.id]))

    assert o3.nombre in response.content.decode('utf8')
    no_positivos = response.context['resultados'].tabla_no_positivos()

    assert no_positivos['blanco'] == {'porcentaje_total': '10.00', 'votos': 10}
    assert no_positivos['positivos']['votos'] == 90


def test_resultados_excluye_metadata(fiscal_client):
    s1, s2 = SeccionFactory.create_batch(2)
    o1, o2 = OpcionFactory.create_batch(2)
    o3 = OpcionFactory(partido=None, tipo='no_positivo')
    o4 = OpcionFactory(nombre='TOTAL', partido=None, tipo='metadata')
    e1 = CategoriaFactory(opciones=[o1, o2, o3, o4])

    m1, *_ = MesaFactory.create_batch(
        3, categorias=[e1], lugar_votacion__circuito__seccion=s1, electores=200
    )
    m2 = MesaFactory(categorias=[e1], lugar_votacion__circuito__seccion=s2, electores=200)

    c1 = CargaFactory(mesa_categoria__mesa=m1, mesa_categoria__categoria=e1, tipo=Carga.TIPOS.total)
    VotoMesaReportadoFactory(opcion=o1, carga=c1, votos=100)
    VotoMesaReportadoFactory(opcion=o2, carga=c1, votos=50)
    VotoMesaReportadoFactory(opcion=o3, carga=c1, votos=10)
    VotoMesaReportadoFactory(opcion=o4, carga=c1, votos=160)
    c1.actualizar_firma()
    c2 = CargaFactory(mesa_categoria__mesa=m2, mesa_categoria__categoria=e1, tipo=Carga.TIPOS.total)
    VotoMesaReportadoFactory(opcion=o1, carga=c2, votos=50)
    VotoMesaReportadoFactory(opcion=o2, carga=c2, votos=100)
    VotoMesaReportadoFactory(opcion=o3, carga=c2, votos=10)
    VotoMesaReportadoFactory(opcion=o4, carga=c2, votos=160)
    c2.actualizar_firma()
    consumir_novedades_y_actualizar_objetos()

    response = fiscal_client.get(reverse('resultados-categoria', args=[e1.id]) + '?tipodesumarizacion=2')
    resultados = response.context['resultados']
    positivos = resultados.tabla_positivos()
    no_positivos = resultados.tabla_no_positivos()

    assert positivos[o1.partido]['votos'] == 150
    assert positivos[o2.partido]['votos'] == 150
    assert no_positivos['Votos Positivos']['votos'] == 300

    assert positivos[o1.partido]['detalle'][o1]['porcentaje_positivos'] == '50.00'
    assert positivos[o2.partido]['detalle'][o2]['porcentaje_positivos'] == '50.00'
    # TODO proyecciones sera re escrito
    # assert positivos[o1.partido]['proyeccion'] == '58.33'
    # assert positivos[o2.partido]['proyeccion'] == '41.67'

    assert no_positivos[o3.nombre] == {'porcentaje_total': '6.25', 'votos': 20}
    assert list(no_positivos.keys()) == [o3.nombre, 'Votos Positivos']


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


def test_permisos_vistas(setup_groups, url_resultados, client):
    u_visualizador = UserFactory()
    visualizador = FiscalFactory(user=u_visualizador)
    g_visualizadores = Group.objects.get(name='visualizadores')
    u_visualizador.groups.add(g_visualizadores)
    u_validador = UserFactory()
    validador = FiscalFactory(user=u_validador)
    g_validadores = Group.objects.get(name='validadores')
    u_validador.groups.add(g_validadores)

    # El usuario visualizador intenta cargar un acta, no debería poder.
    client.login(username=u_visualizador.username, password='password')
    response = client.get(reverse('siguiente-accion'))
    assert response.status_code == 302 and response.url.startswith('/permission-denied')

    # Sí debería poder ver resultados.
    response = client.get(url_resultados, {'distrito': 1})
    assert response.status_code == 200

    # El usuario validador intenta cargar un acta, sí debería poder
    client.login(username=u_validador.username, password='password')
    response = client.get(reverse('siguiente-accion'))
    assert response.status_code == 200
