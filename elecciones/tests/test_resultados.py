from django.conf import settings
from django.urls import reverse
from django.contrib.auth.models import Group
from http import HTTPStatus
from elecciones.models import Categoria, MesaCategoria, Carga, Seccion, Opcion, OPCIONES_A_CONSIDERAR

from .factories import (
    UserFactory,
    CategoriaFactory,
    LugarVotacionFactory,
    FiscalFactory,
    OpcionFactory,
    MesaFactory,
    MesaCategoriaFactory,
    IdentificacionFactory,
    VotoMesaReportadoFactory,
    CargaFactory,
)
from adjuntos.models import Identificacion
from adjuntos.consolidacion import consumir_novedades_identificacion
from .test_models import consumir_novedades_y_actualizar_objetos
from .utils import tecnica_proyeccion, cargar_votos
from elecciones.tests.conftest import setup_groups, fiscal_client_from_fiscal    # noqa


def test_resultados_pide_login(db, client, url_resultados):
    response = client.get(url_resultados)
    assert response.status_code == 302
    query = f'?next={url_resultados}'
    assert response.url == reverse('login') + query


def test_resultados_pide_visualizador(db, fiscal_client, admin_user, url_resultados):
    g = Group.objects.get(name='visualizadores')
    admin_user.groups.remove(g)
    response = fiscal_client.get(url_resultados)
    assert response.status_code == 403          # permission denied


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
    response = fiscal_client.get(url_resultados, {'opcionaConsiderar': 'todas', 'mesa': mesa1.id})
    resultados = response.context['resultados']
    assert resultados.electores() == 120
    #assert b'<td title="Electores">120</td>' in response.content


def test_electores_filtro_mesa_multiple_categoria(fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=120)  # mesa2 solo de la categoria 1
    e1 = CategoriaFactory()
    mesa1.categoria_add(e1)  # mesa 1 tambien está asociada a e1
    url = reverse('resultados-categoria', args=[e1.id])

    response = fiscal_client.get(url, {'opcionaConsiderar': 'todas', 'mesa': mesa1.id})
    resultados = response.context['resultados']
    assert resultados.electores() == 120
    #assert b'<td title="Electores">120</td>' in response.content


def test_electores_filtro_escuela(url_resultados, fiscal_client):
    e = LugarVotacionFactory()
    MesaFactory(electores=120, lugar_votacion=e)
    MesaFactory(electores=80, lugar_votacion=e)
    MesaFactory(electores=90)
    response = fiscal_client.get(url_resultados, {'opcionaConsiderar': 'todas', 'lugar_de_votacion': e.id})
    resultados = response.context['resultados']
    assert resultados.electores() == 200
    #assert b'<td title="Electores">200</td>' in response.content


def test_electores_filtro_circuito(url_resultados, fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=90)
    response = fiscal_client.get(url_resultados, {'opcionaConsiderar': 'todas', 'circuito': mesa1.lugar_votacion.circuito.id})
    resultados = response.context['resultados']
    assert resultados.electores() == 120
    #assert b'<td title="Electores">120</td>' in response.content


def test_electores_filtro_seccion(url_resultados, fiscal_client):
    mesa1 = MesaFactory(electores=120)
    MesaFactory(electores=90)
    response = fiscal_client.get(url_resultados, {'opcionaConsiderar': 'todas', 'seccion': mesa1.lugar_votacion.circuito.seccion.id})
    resultados = response.context['resultados']
    assert resultados.electores() == 120
    #assert b'<td title="Electores">120</td>' in response.content


def test_electores_filtro_distrito(url_resultados, fiscal_client):
    m2 = MesaFactory(electores=90, lugar_votacion__circuito__seccion__distrito__nombre='otro')
    response = fiscal_client.get(
        url_resultados, {'opcionaConsiderar': 'todas', 'distrito': m2.lugar_votacion.circuito.seccion.distrito.id}
    )
    resultados = response.context['resultados']
    assert resultados.electores() == 90
    #assert b'<td title="Electores">90</td>' in response.content


def test_electores_sin_filtro(url_resultados, fiscal_client):
    response = fiscal_client.get(url_resultados, {'opcionaConsiderar': 'todas'})
    resultados = response.context['resultados']
    assert resultados.electores() == 800
    #assert b'<td title="Electores">800</td>' in response.content


def test_resultados_parciales_generales(carta_marina, url_resultados, fiscal_client):
    # Seteamos el modo de elección como PASO; por lo tanto
    # los porcentajes que deberíamos visualizar son los porcentaje_validos
    settings.MODO_ELECCION = settings.ME_OPCION_GEN

    # resultados para mesa 1
    m1, m2, m3, *otras_mesas = carta_marina
    categoria = m1.categorias.get()  # sólo default
    # opciones a partido
    o1, o2, o3, o4 = categoria.opciones.filter(partido__isnull=False)
    # la opción 4 pasa a ser del mismo partido que la 1
    o4.partido = o1.partido
    o4.save()

    blanco = Opcion.blancos()
    total = Opcion.total_votos()
    nulos = Opcion.nulos()

    mc1 = MesaCategoria.objects.get(mesa=m1, categoria=categoria)
    mc2 = MesaCategoria.objects.get(mesa=m2, categoria=categoria)
    mc3 = MesaCategoria.objects.get(mesa=m3, categoria=categoria)
    c1 = CargaFactory(mesa_categoria=mc1, tipo=Carga.TIPOS.parcial)
    c2 = CargaFactory(mesa_categoria=mc3, tipo=Carga.TIPOS.parcial)
    c3 = CargaFactory(mesa_categoria=mc2, tipo=Carga.TIPOS.parcial)
    consumir_novedades_y_actualizar_objetos([m1, m2, m3])

    VotoMesaReportadoFactory(carga=c1, opcion=o1, votos=20)
    VotoMesaReportadoFactory(carga=c1, opcion=o2, votos=30)
    VotoMesaReportadoFactory(carga=c1, opcion=o3, votos=40)
    VotoMesaReportadoFactory(carga=c1, opcion=o4, votos=5)

    # votaron 95/100 personas
    VotoMesaReportadoFactory(carga=c1, opcion=blanco, votos=5)
    VotoMesaReportadoFactory(carga=c1, opcion=total, votos=100)

    VotoMesaReportadoFactory(carga=c2, opcion=o1, votos=10)
    VotoMesaReportadoFactory(carga=c2, opcion=o2, votos=40)
    VotoMesaReportadoFactory(carga=c2, opcion=o3, votos=50)
    VotoMesaReportadoFactory(carga=c2, opcion=o4, votos=20)

    # votaron 120/120 personas
    VotoMesaReportadoFactory(carga=c2, opcion=blanco, votos=0)
    VotoMesaReportadoFactory(carga=c2, opcion=total, votos=120)

    # votaron 45 / 100 personas
    VotoMesaReportadoFactory(carga=c3, opcion=blanco, votos=40)
    VotoMesaReportadoFactory(carga=c3, opcion=nulos, votos=5)
    VotoMesaReportadoFactory(carga=c3, opcion=total, votos=45)

    c1.actualizar_firma()
    c2.actualizar_firma()
    c3.actualizar_firma()
    assert c1.es_testigo.exists()
    assert c2.es_testigo.exists()
    assert c3.es_testigo.exists()

    response = fiscal_client.get(
        url_resultados + f'?opcionaConsiderar={OPCIONES_A_CONSIDERAR.prioritarias}'
    )
    resultados = response.context['resultados']

    positivos = resultados.tabla_positivos()
    # se ordena de acuerdo al que va ganando
    assert list(positivos.keys()) == [o3.partido, o2.partido, o1.partido]

    total_positivos = resultados.total_positivos()
    total_blancos = resultados.total_blancos()

    assert total_positivos == 215  # 20 + 30 + 40 + 5 + 20 + 10 + 40 + 50
    assert total_blancos == 45  # 5 + 0

    # cuentas
    assert positivos[o3.partido]['votos'] == 40 + 50
    # (40 + 50) / total_positivos
    assert positivos[o3.partido]['porcentaje_positivos'] == '41.86'
    # (40 + 50) / total_positivos + total_blanco
    assert positivos[o3.partido]['porcentaje_validos'] == '34.62'
    assert positivos[o2.partido]['votos'] == 30 + 40
    # (30 + 40) / total_positivos
    assert positivos[o2.partido]['porcentaje_positivos'] == '32.56'
    # (30 + 40) / total_positivos + total_blanco
    assert positivos[o2.partido]['porcentaje_validos'] == '26.92'
    assert positivos[o1.partido]['votos'] == 10 + 20 + 20 + 5
    # (20 + 5 + 10 + 20) / total_positivos
    assert positivos[o1.partido]['porcentaje_positivos'] == '25.58'
    # (20 + 5 + 10 + 20) / total_positivos + total_blanco
    assert positivos[o1.partido]['porcentaje_validos'] == '21.15'

    # todos los positivos suman 100
    assert sum(float(v['porcentaje_positivos']) for v in positivos.values()) == 100.0

    # votos de partido 1 son iguales a los de o1 + o4
    assert positivos[o1.partido]['votos'] == sum(
        x['votos'] for x in positivos[o4.partido]['detalle'].values()
    )

    content = response.content.decode('utf8')

    assert f'<td id="votos_{o1.partido.id}" class="dato_entero">55</td>' in content
    assert f'<td id="votos_{o2.partido.id}" class="dato_entero">70</td>' in content
    assert f'<td id="votos_{o3.partido.id}" class="dato_entero">90</td>' in content

    # Deberíamos visualizar los porcentajes positivos.
    assert f'<td id="porcentaje_{o1.partido.id}" class="dato">25.58%</td>' in content
    assert f'<td id="porcentaje_{o2.partido.id}" class="dato">32.56%</td>' in content
    assert f'<td id="porcentaje_{o3.partido.id}" class="dato">41.86%</td>' in content

    total_electores = sum(m.electores for m in carta_marina)

    assert resultados.electores() == total_electores
    assert resultados.total_positivos() == 215  # 20 + 30 + 40 + 5 + 20 + 10 + 40 + 50
    assert resultados.porcentaje_positivos() == '81.13'
    assert resultados.porcentaje_mesas_escrutadas() == '37.50'  # 3 de 8
    assert resultados.votantes() == 265
    assert resultados.electores_en_mesas_escrutadas() == 320
    assert resultados.porcentaje_escrutado() == f'{100 * 320 / total_electores:.2f}'
    assert resultados.porcentaje_participacion() == f'{100 * 265/ 320:.2f}'  # Es sobre escrutado.

    assert resultados.total_blancos() == 45
    assert resultados.porcentaje_blancos() == '16.98'

    assert resultados.total_nulos() == 5
    assert resultados.porcentaje_nulos() == '1.89'

    assert resultados.total_votos() == 265
    assert resultados.electores() == 800
    assert resultados.total_sobres() == 0

    columna_datos = [
        #('Electores', resultados.electores()),
        #('Escrutados', resultados.electores_en_mesas_escrutadas()),
        #('% Escrutado', f'{resultados.porcentaje_escrutado()} %'),
        ('Votantes', resultados.votantes()),
        ('Positivos', resultados.total_positivos()),
        #('% Participación', f'{resultados.porcentaje_participacion()} %'),
    ]
    for variable, valor in columna_datos:
        assert f'<td title="{variable}">{valor}</td>' in content


def test_resultados_parciales_paso(carta_marina, url_resultados, fiscal_client):
    # Seteamos el modo de elección como PASO; por lo tanto
    # los porcentajes que deberíamos visualizar son los porcentaje_validos
    settings.MODO_ELECCION = settings.ME_OPCION_PASO

    # resultados para mesa 1
    m1, m2, m3, *otras_mesas = carta_marina
    categoria = m1.categorias.get()  # sólo default
    # opciones a partido
    o1, o2, o3, o4 = categoria.opciones.filter(partido__isnull=False)
    # la opción 4 pasa a ser del mismo partido que la 1
    o4.partido = o1.partido
    o4.save()

    blanco = Opcion.blancos()
    total = Opcion.total_votos()
    nulos = Opcion.nulos()

    mc1 = MesaCategoria.objects.get(mesa=m1, categoria=categoria)
    mc2 = MesaCategoria.objects.get(mesa=m2, categoria=categoria)
    mc3 = MesaCategoria.objects.get(mesa=m3, categoria=categoria)
    c1 = CargaFactory(mesa_categoria=mc1, tipo=Carga.TIPOS.parcial)
    c2 = CargaFactory(mesa_categoria=mc3, tipo=Carga.TIPOS.parcial)
    c3 = CargaFactory(mesa_categoria=mc2, tipo=Carga.TIPOS.parcial)
    consumir_novedades_y_actualizar_objetos([m1, m2, m3])

    VotoMesaReportadoFactory(carga=c1, opcion=o1, votos=20)
    VotoMesaReportadoFactory(carga=c1, opcion=o2, votos=30)
    VotoMesaReportadoFactory(carga=c1, opcion=o3, votos=40)
    VotoMesaReportadoFactory(carga=c1, opcion=o4, votos=5)

    # votaron 95/100 personas
    VotoMesaReportadoFactory(carga=c1, opcion=blanco, votos=5)
    VotoMesaReportadoFactory(carga=c1, opcion=total, votos=100)

    VotoMesaReportadoFactory(carga=c2, opcion=o1, votos=10)
    VotoMesaReportadoFactory(carga=c2, opcion=o2, votos=40)
    VotoMesaReportadoFactory(carga=c2, opcion=o3, votos=50)
    VotoMesaReportadoFactory(carga=c2, opcion=o4, votos=20)

    # votaron 120/120 personas
    VotoMesaReportadoFactory(carga=c2, opcion=blanco, votos=0)
    VotoMesaReportadoFactory(carga=c2, opcion=total, votos=120)

    # votaron 45 / 100 personas
    VotoMesaReportadoFactory(carga=c3, opcion=blanco, votos=40)
    VotoMesaReportadoFactory(carga=c3, opcion=nulos, votos=5)
    VotoMesaReportadoFactory(carga=c3, opcion=total, votos=45)

    c1.actualizar_firma()
    c2.actualizar_firma()
    c3.actualizar_firma()
    assert c1.es_testigo.exists()
    assert c2.es_testigo.exists()
    assert c3.es_testigo.exists()

    response = fiscal_client.get(
        url_resultados + f'?opcionaConsiderar={OPCIONES_A_CONSIDERAR.prioritarias}'
    )
    resultados = response.context['resultados']

    positivos = resultados.tabla_positivos()
    # se ordena de acuerdo al que va ganando
    assert list(positivos.keys()) == [o3.partido, o2.partido, o1.partido]

    total_positivos = resultados.total_positivos()
    total_blancos = resultados.total_blancos()

    assert total_positivos == 215  # 20 + 30 + 40 + 5 + 20 + 10 + 40 + 50
    assert total_blancos == 45  # 5 + 0

    # cuentas
    assert positivos[o3.partido]['votos'] == 40 + 50
    # (40 + 50) / total_positivos
    assert positivos[o3.partido]['porcentaje_positivos'] == '41.86'
    # (40 + 50) / total_positivos + total_blanco
    assert positivos[o3.partido]['porcentaje_validos'] == '34.62'
    assert positivos[o2.partido]['votos'] == 30 + 40
    # (30 + 40) / total_positivos
    assert positivos[o2.partido]['porcentaje_positivos'] == '32.56'
    # (30 + 40) / total_positivos + total_blanco
    assert positivos[o2.partido]['porcentaje_validos'] == '26.92'
    assert positivos[o1.partido]['votos'] == 10 + 20 + 20 + 5
    # (20 + 5 + 10 + 20) / total_positivos
    assert positivos[o1.partido]['porcentaje_positivos'] == '25.58'
    # (20 + 5 + 10 + 20) / total_positivos + total_blanco
    assert positivos[o1.partido]['porcentaje_validos'] == '21.15'

    # todos los positivos suman 100
    assert sum(float(v['porcentaje_positivos']) for v in positivos.values()) == 100.0

    # votos de partido 1 son iguales a los de o1 + o4
    assert positivos[o1.partido]['votos'] == sum(
        x['votos'] for x in positivos[o4.partido]['detalle'].values()
    )

    content = response.content.decode('utf8')

    assert f'<td id="votos_{o1.partido.id}" class="dato_entero">55</td>' in content
    assert f'<td id="votos_{o2.partido.id}" class="dato_entero">70</td>' in content
    assert f'<td id="votos_{o3.partido.id}" class="dato_entero">90</td>' in content

    # Deberíamos visualizar los porcentajes sin nulos.
    assert f'<td id="porcentaje_{o1.partido.id}" class="dato">21.15%</td>' in content
    assert f'<td id="porcentaje_{o2.partido.id}" class="dato">26.92%</td>' in content
    assert f'<td id="porcentaje_{o3.partido.id}" class="dato">34.62%</td>' in content

    total_electores = sum(m.electores for m in carta_marina)

    assert resultados.electores() == total_electores
    assert resultados.total_positivos() == 215  # 20 + 30 + 40 + 5 + 20 + 10 + 40 + 50
    assert resultados.porcentaje_positivos() == '81.13'
    assert resultados.porcentaje_mesas_escrutadas() == '37.50'  # 3 de 8
    assert resultados.votantes() == 265
    assert resultados.electores_en_mesas_escrutadas() == 320
    assert resultados.porcentaje_escrutado() == f'{100 * 320 / total_electores:.2f}'
    assert resultados.porcentaje_participacion() == f'{100 * 265/ 320:.2f}'  # Es sobre escrutado.

    assert resultados.total_blancos() == 45
    assert resultados.porcentaje_blancos() == '16.98'

    assert resultados.total_nulos() == 5
    assert resultados.porcentaje_nulos() == '1.89'

    assert resultados.total_votos() == 265
    #assert resultados.electores() == 800
    assert resultados.total_sobres() == 0

    columna_datos = [
        #('Electores', resultados.electores()),
        #('Escrutados', resultados.electores_en_mesas_escrutadas()),
        #('% Escrutado', f'{resultados.porcentaje_escrutado()} %'),
        ('Votantes', resultados.votantes()),
        ('Positivos', resultados.total_positivos()),
        #('% Participación', f'{resultados.porcentaje_participacion()} %'),
    ]
    for variable, valor in columna_datos:
        assert f'<td title="{variable}">{valor}</td>' in content


def test_solo_total_confirmado_y_sin_confirmar(carta_marina, url_resultados, fiscal_client):
    m1, _, m3, *_ = carta_marina
    categoria = m1.categorias.get()
    # opciones a partido
    blanco = Opcion.blancos()

    c1 = CargaFactory(mesa_categoria__mesa=m1, mesa_categoria__categoria=categoria, tipo=Carga.TIPOS.total)
    VotoMesaReportadoFactory(carga=c1, opcion=blanco, votos=20)
    c1.actualizar_firma()
    mc = c1.mesa_categoria
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.carga_testigo == c1
    assert mc.status == MesaCategoria.STATUS.total_sin_consolidar

    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        '?tipoDeAgregacion=todas_las_cargas&opcionaConsiderar=todas'
    )
    resultados = response.context['resultados']
    assert resultados.tabla_no_positivos()[blanco.nombre_corto]['votos'] == 20
    assert resultados.total_mesas_escrutadas() == 1

    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        '?tipoDeAgregacion=solo_consolidados&opcionaConsiderar=todas'
    )
    resultados = response.context['resultados']
    assert resultados.tabla_no_positivos()[blanco.nombre_corto] == {'votos': 0, 'porcentaje_total': '-'}
    assert resultados.total_mesas_escrutadas() == 0

    c2 = CargaFactory(mesa_categoria__mesa=m1, mesa_categoria__categoria=categoria, tipo=Carga.TIPOS.total)
    VotoMesaReportadoFactory(carga=c2, opcion=blanco, votos=20)
    c2.actualizar_firma()

    consumir_novedades_y_actualizar_objetos([mc])
    assert mc == c2.mesa_categoria
    # la carga testigo sigue siendo la primera coincidentes
    assert mc.carga_testigo == c1
    assert mc.status == MesaCategoria.STATUS.total_consolidada_dc

    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        '?tipoDeAgregacion=todas_las_cargas&opcionaConsiderar=todas'
    )
    resultados = response.context['resultados']
    assert resultados.tabla_no_positivos()[blanco.nombre_corto]['votos'] == 20
    assert resultados.total_mesas_escrutadas() == 1

    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        '?tipoDeAgregacion=solo_consolidados&opcionaConsiderar=todas'
    )
    resultados = response.context['resultados']
    assert resultados.tabla_no_positivos()[blanco.nombre_corto]['votos'] == 20
    assert resultados.total_mesas_escrutadas() == 1


def test_parcial_confirmado(carta_marina, url_resultados, fiscal_client):
    m1, _, m3, *_ = carta_marina
    categoria = m1.categorias.get()
    # opciones a partido
    blanco = Opcion.blancos()

    c1 = CargaFactory(tipo=Carga.TIPOS.parcial, mesa_categoria__mesa=m1, mesa_categoria__categoria=categoria)
    VotoMesaReportadoFactory(carga=c1, opcion=blanco, votos=20)
    c1.actualizar_firma()
    consumir_novedades_y_actualizar_objetos()

    # TODO dependiendo de lo que se quiera la url podria ser algo como por ejemplo:
    # response = fiscal_client.get(reverse('resultados-categoria', args=[categoria.id]) +
    #       '?tipoDeAgregacion=solo_consolidados&opcionaConsiderar=prioritarias')
    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        '?tipoDeAgregacion=solo_consolidados&opcionaConsiderar=prioritarias'
    )

    resultados = response.context['resultados']
    # la carga está en status sin_confirmar
    assert resultados.tabla_no_positivos()[blanco.nombre_corto] == {'votos': 0, 'porcentaje_total': '-'}
    assert resultados.total_mesas_escrutadas() == 0

    c2 = CargaFactory(tipo=Carga.TIPOS.parcial, mesa_categoria__mesa=m1, mesa_categoria__categoria=categoria)
    VotoMesaReportadoFactory(carga=c2, opcion=blanco, votos=20)
    c2.actualizar_firma()
    mc = c1.mesa_categoria
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc == c2.mesa_categoria
    assert mc.carga_testigo in [c1, c2]
    assert mc.status == MesaCategoria.STATUS.parcial_consolidada_dc

    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        '?tipoDeAgregacion=solo_consolidados&opcionaConsiderar=prioritarias'
    )
    resultados = response.context['resultados']
    # Como tenemos dos cargas confirmadas, se modifica el resultado.
    assert resultados.tabla_no_positivos()[blanco.nombre_corto]['votos'] == 20
    assert resultados.total_mesas_escrutadas() == 1

    c3 = CargaFactory(tipo=Carga.TIPOS.parcial, mesa_categoria__mesa=m3, mesa_categoria__categoria=categoria)
    VotoMesaReportadoFactory(carga=c3, opcion=blanco, votos=10)
    c3.actualizar_firma()
    consumir_novedades_y_actualizar_objetos([mc])
    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        '?tipoDeAgregacion=solo_consolidados&opcionaConsiderar=prioritarias'
    )
    resultados = response.context['resultados']
    # c3 no está confirmada, no varía el resultado.
    assert resultados.tabla_no_positivos()[blanco.nombre_corto]['votos'] == 20
    assert resultados.total_mesas_escrutadas() == 1

    c4 = CargaFactory(tipo=Carga.TIPOS.parcial, mesa_categoria__mesa=m3, mesa_categoria__categoria=categoria)
    VotoMesaReportadoFactory(carga=c4, opcion=blanco, votos=10)
    c4.actualizar_firma()
    consumir_novedades_y_actualizar_objetos([mc])

    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        '?tipoDeAgregacion=solo_consolidados&opcionaConsiderar=prioritarias'
    )
    resultados = response.context['resultados']
    # Ahora sí varía.
    assert resultados.tabla_no_positivos()[blanco.nombre_corto]['votos'] == 30
    assert resultados.total_mesas_escrutadas() == 2


def test_siguiente_accion_cargar_acta(client, setup_groups, settings):
    c = CategoriaFactory(nombre='default')
    m1 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    m2 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    mc1 = MesaCategoriaFactory(mesa=m1, categoria=c)
    mc2 = MesaCategoriaFactory(mesa=m2, categoria=c)
    consumir_novedades_identificacion()

    fiscales = FiscalFactory.create_batch(4)

    # Todas estas veces debería darme la misma.
    for i in range(settings.MIN_COINCIDENCIAS_CARGAS):
        fiscal_client = fiscal_client_from_fiscal(client, fiscales[i])
        response = fiscal_client.get(reverse('siguiente-accion'))
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse('carga-total', args=(mc1.id, ))
        mc1.refresh_from_db()
        assert mc1.cant_fiscales_asignados == i + 1
        # Cerramos la sesión para que el client pueda reutilizarse sin que nos diga
        # que ya estamos logueados.
        fiscal_client.logout()

    # Ahora la siguiente.
    fiscal_client = fiscal_client_from_fiscal(client, fiscales[i+1])
    response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('carga-total', args=(mc2.id, ))
    fiscal_client.logout()

    # Devuelvo la primera y pido de nuevo. Debería volver a darme la primera.
    mc1.desasignar_a_fiscal()
    fiscal_client = fiscal_client_from_fiscal(client, fiscales[i+2])
    response = fiscal_client.get(reverse('siguiente-accion'))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse('carga-total', args=(mc1.id, ))


def test_resultados_no_positivos(fiscal_client):
    o1, o2 = OpcionFactory.create_batch(2)
    e1 = CategoriaFactory(opciones=[o1, o2])

    opcion_blanco = Opcion.blancos()
    opcion_total = Opcion.total_votos()
    opcion_sobres = Opcion.sobres()

    m1 = MesaFactory(categorias=[e1], electores=200)
    c1 = CargaFactory(mesa_categoria__categoria=e1, mesa_categoria__mesa=m1, tipo=Carga.TIPOS.parcial)
    VotoMesaReportadoFactory(opcion=o1, carga=c1, votos=50)
    VotoMesaReportadoFactory(opcion=o2, carga=c1, votos=40)
    VotoMesaReportadoFactory(opcion=opcion_blanco, carga=c1, votos=10)
    VotoMesaReportadoFactory(opcion=opcion_total, carga=c1, votos=100)
    VotoMesaReportadoFactory(opcion=opcion_sobres, carga=c1, votos=110)
    c1.actualizar_firma()
    consumir_novedades_y_actualizar_objetos()

    response = fiscal_client.get(
        reverse('resultados-categoria', args=[e1.id]) + '?opcionaConsiderar=prioritarias'
    )

    resultados = response.context['resultados']

    assert resultados.total_positivos() == 90
    assert resultados.total_blancos() == 10
    assert resultados.total_votos() == 100
    assert resultados.total_sobres() == 110
    assert resultados.porcentaje_positivos() == '90.00'
    assert resultados.porcentaje_blancos() == '10.00'
    assert resultados.porcentaje_nulos() == '0.00'


def test_resultados_excluye_metadata(fiscal_client, carta_marina):
    s1, s2 = Seccion.objects.all()
    o1, o2 = OpcionFactory.create_batch(2)
    e1 = CategoriaFactory(opciones=[o1, o2])

    m1, *_ = MesaFactory.create_batch(
        3, categorias=[e1], lugar_votacion__circuito__seccion=s1, electores=200
    )
    m2 = MesaFactory(categorias=[e1], lugar_votacion__circuito__seccion=s2, electores=200)

    c1 = CargaFactory(mesa_categoria__mesa=m1, mesa_categoria__categoria=e1, tipo=Carga.TIPOS.total)
    cargar_votos(c1, {
        o1: 100,
        o2: 50,
        Opcion.blancos(): 10,
        Opcion.total_votos(): 160,
    })

    c2 = CargaFactory(mesa_categoria__mesa=m2, mesa_categoria__categoria=e1, tipo=Carga.TIPOS.total)
    cargar_votos(c2, {
        o1: 50,
        o2: 100,
        Opcion.blancos(): 10,
        Opcion.total_votos(): 160,
    })
    consumir_novedades_y_actualizar_objetos()

    tecnica = tecnica_proyeccion()
    response = fiscal_client.get(
        reverse('resultados-categoria', args=[e1.id]) +
        f'?tipoDeAgregacion=todas_las_cargas&opcionaConsiderar=todas&tecnicaDeProyeccion={tecnica.id}'
    )

    resultados = response.context['resultados']
    positivos = resultados.tabla_positivos()
    no_positivos = resultados.tabla_no_positivos()

    # PROYECCION:
    # la seccion 2 esta sobre representada por el momento (está al 100%)
    # en la seccion 1 todo se multiplica x 3 (tengo 1 de 3 mesas)
    # proyeccion de la seccion 1 es partido 1 = 100 * 3 (3=mesas totales/mesas actuales) = 300
    #                               partido 2 =  50 * 3 = 150
    # proyeccion o1 = 350 + 50 = 350
    # proyeccion o2 = 150 + 100 = 250
    # votos proyectados = 1200
    # %o1 = 350 / 600 = 56.58%
    # %o2 = 250 / 600 = 41.67%
    assert positivos[o1.partido]['detalle'][o1.str_frontend()]['porcentaje_positivos'] == '58.33'
    assert positivos[o2.partido]['detalle'][o2.str_frontend()]['porcentaje_positivos'] == '41.67'

    # Votos en blanco proyectados = 10 * 3 (s1) + 10 (s2) = 40
    # %blancos = 40 / (600 + 40) = 6.25%
    # %positivos = 600 / (600 + 40) = 93.75%
    assert no_positivos[Opcion.blancos().nombre_corto]['porcentaje_total'] == '6.25'
    assert no_positivos[settings.KEY_VOTOS_POSITIVOS]['porcentaje_total'] == '93.75'


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
    FiscalFactory(user=u_visualizador)
    g_visualizadores = Group.objects.get(name='visualizadores')
    u_visualizador.groups.add(g_visualizadores)
    u_validador = UserFactory()
    FiscalFactory(user=u_validador)
    g_validadores = Group.objects.get(name='validadores')
    u_validador.groups.add(g_validadores)

    # El usuario visualizador intenta cargar un acta, no debería poder.
    client.login(username=u_visualizador.username, password='password')
    response = client.get(reverse('siguiente-accion'))
    assert response.status_code == 302 and response.url.startswith('/permission-denied')

    # Sí debería poder ver resultados.
    response = client.get(url_resultados, {'opcionaConsiderar': 'todas', 'distrito': 1})
    assert response.status_code == 200

    client.logout()
    # El usuario validador intenta cargar un acta, sí debería poder
    client.login(username=u_validador.username, password='password')
    response = client.get(reverse('siguiente-accion'))
    assert response.status_code == 200


def test_categorias_sensible(setup_groups, client):
    u_visualizador = UserFactory()
    _ = FiscalFactory(user=u_visualizador)
    g_visualizadores = Group.objects.get(name='visualizadores')
    u_visualizador.groups.add(g_visualizadores)

    u_visualizador_sensible = UserFactory()
    _ = FiscalFactory(user=u_visualizador_sensible)
    g_visualizadores_sensible = Group.objects.get(name='visualizadores_sensible')
    u_visualizador_sensible.groups.add(g_visualizadores_sensible)
    u_visualizador_sensible.groups.add(g_visualizadores)

    c = CategoriaFactory(nombre='default', sensible=False)
    c_url = reverse('resultados-categoria', args=[c.id])

    c = CategoriaFactory(nombre='default-sensible', sensible=True)
    c_sensible_url = reverse('resultados-categoria', args=[c.id])

    # El usuario visualizador intenta ver resultado sensible, no debería poder.
    client.login(username=u_visualizador.username, password='password')
    response = client.get(c_sensible_url, {'opcionaConsiderar': 'todas'})
    assert response.status_code == 403

    # Sí debería poder ver resultados.
    response = client.get(c_url, {'opcionaConsiderar': 'todas'})
    assert response.status_code == 200

    client.logout()

    # El usuario visualizador sensible puede ver resultado sensible.
    client.login(username=u_visualizador_sensible.username, password='password')
    response = client.get(c_sensible_url, {'opcionaConsiderar': 'todas'})
    assert response.status_code == 200

    # El usuario visualizador sensible puede ver resultado no sensible.
    response = client.get(c_url, {'opcionaConsiderar': 'todas'})
    assert response.status_code == 200
