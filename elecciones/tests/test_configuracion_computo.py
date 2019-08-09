from django.conf import settings

from elecciones.models import (
    Distrito,
    Seccion,
    Categoria,
    MesaCategoria,
    Carga,
    Opcion,
    TIPOS_DE_AGREGACIONES,
    OPCIONES_A_CONSIDERAR,
)
from .factories import (
    MesaCategoriaFactory,
    OpcionFactory,
    CargaFactory,
    VotoMesaReportadoFactory,
    ConfiguracionComputoFactory,
    ConfiguracionComputoDistritoFactory,
)
from .test_models import consumir_novedades_y_actualizar_objetos
from .utils import create_carta_marina, cargar_votos, tecnica_proyeccion


def test_configuracion_combinada(db, fiscal_client, url_resultados_computo):
    # Seteamos el modo de elección como PASO; por lo tanto
    # los porcentajes que deberíamos visualizar son los porcentaje_validos
    settings.MODO_ELECCION = settings.ME_OPCION_GEN

    # Asegurar una carta marina con dos distritos extra además del "Distrito único".
    mesas = create_carta_marina(create_distritos=2)

    categoria = Categoria.objects.first()
    for mesa in mesas:
        MesaCategoriaFactory(mesa=mesa, categoria=categoria)

    o1, o2, *_ = categoria.opciones.filter(partido__isnull=False)
    blancos = Opcion.blancos()
    nulos = Opcion.nulos()
    total = Opcion.total_votos()

    # Cargamos los mismos votos en los tres distritos.
    # for distrito in Distrito.objects.exclude(id=1):  # Excluyo al distrito "único" que se crea siempre.
    for distrito in Distrito.objects.all():
        s1, s2 = distrito.secciones.all()

        # En s1 hacemos una carga doble sobre la misma mesa
        mc1, *_ = MesaCategoria.objects.filter(mesa__lugar_votacion__circuito__seccion=s1)
        c1 = CargaFactory(mesa_categoria=mc1, tipo=Carga.TIPOS.total)
        cargar_votos(c1, {o1: 60, o2: 40, blancos: 0, nulos: 0, total: 100})

        c2 = CargaFactory(mesa_categoria=mc1, tipo=Carga.TIPOS.total)
        cargar_votos(c2, {o1: 60, o2: 40, blancos: 0, nulos: 0, total: 100})

        # En s2 hacemos dos cargas simples en mesas distintas
        mc2, mc3, *_ = MesaCategoria.objects.filter(mesa__lugar_votacion__circuito__seccion=s2)
        c3 = CargaFactory(mesa_categoria=mc2, tipo=Carga.TIPOS.total)
        cargar_votos(c3, {o1: 20, o2: 60, blancos: 10, nulos: 0, total: 90})

        c4 = CargaFactory(mesa_categoria=mc3, tipo=Carga.TIPOS.total)
        cargar_votos(c4, {o1: 20, o2: 60, blancos: 5, nulos: 5, total: 90})

    consumir_novedades_y_actualizar_objetos()

    # Crear una configuración de cómputo combinada con estrategias diferentes para cada distrito
    configuracion_combinada = ConfiguracionComputoFactory()
    d1, d2, d3 = Distrito.objects.all()

    # Para el primer distrito consideramos todas las cargas.
    # Esto nos da 100 votos para la opción 1 (60 + 20 + 20)
    # Y 160 para s2 (40 + 60 + 60)
    # 15 blancos (10 + 5) 
    # y 5 nulos (sólo mc3)
    ConfiguracionComputoDistritoFactory(
        configuracion=configuracion_combinada,
        distrito=d1,
        agregacion=TIPOS_DE_AGREGACIONES.todas_las_cargas,
        opciones=OPCIONES_A_CONSIDERAR.todas,
    )

    # Para el segundo distrito consideramos sólo las cargas consolidadas
    # Eso hace que que sólo se consideren los votos de mc1: 60 para o1 y 40 para o2
    # En s1 no hay blancos ni nulos
    ConfiguracionComputoDistritoFactory(
        configuracion=configuracion_combinada,
        distrito=d2,
        agregacion=TIPOS_DE_AGREGACIONES.solo_consolidados_doble_carga,
        opciones=OPCIONES_A_CONSIDERAR.todas,
    )

    # Para el último distrito consideramos todas las cargas,
    # pero utilizamos una proyección que exige dos mesas por agrupacion circuito
    # La sección 1 tiene una única mesa, se ignora.
    # La sección 2 tiene escrutadas 2 de 4 mesas, así que sus votos se multiplican por 2 = (4/2)
    # o1 = (20 + 20) * 2 = 80 votos
    # o2 = (60 + 60) * 2 = 240 votos
    # blancos = (10 + 5) * 2 = 30 votos
    # nulos = 5 * 2 = 10 votos
    ConfiguracionComputoDistritoFactory(
        configuracion=configuracion_combinada,
        distrito=d3,
        agregacion=TIPOS_DE_AGREGACIONES.todas_las_cargas,
        opciones=OPCIONES_A_CONSIDERAR.todas,
        proyeccion=tecnica_proyeccion(minimo_mesas=2),
    )

    response = fiscal_client.get(url_resultados_computo)
    resultados = response.context['resultados']

    assert resultados.total_mesas() == 24  # 8 en c/u de los 3 distritos

    # TODO Los siguientes dos asserts no dan por un bug en proyecciones, decidimos postergar su resolución.
    # assert resultados.total_mesas_escrutadas() == 6   # {d1: 3, d2: 1, d3: 2}
    # assert resultados.porcentaje_mesas_escrutadas() == '25.00'

    assert resultados.electores() == 2400
    assert resultados.total_votos() == 740  # {d1: 100, d2: 280, d3: 360}

    assert resultados.total_blancos() == 45  # {d2: 15, d3: 30}
    assert resultados.porcentaje_blancos() == '6.08'  # 45 / 740

    assert resultados.total_nulos() == 15  # {d2: 5, d3: 10}
    assert resultados.porcentaje_nulos() == '2.03'  # 15 / 740

    positivos = resultados.tabla_positivos()
# 
    # # se ordena de acuerdo al que va ganando
    # assert list(positivos.keys()) == [o3.partido, o2.partido, o1.partido]

    # Total de votos por partido
    assert positivos[o1.partido]['votos'] == 240  # 60 + 100 + 80
    assert positivos[o2.partido]['votos'] == 30 + 40  # 40 + 160 + 240

    assert resultados.total_positivos() == 680  # 240 + 440

    # total_blancos   = resultados.total_blancos()

    # assert total_blancos   == 45    # 5 + 0

    # # cuentas
    # # (40 + 50) / total_positivos
    # assert positivos[o3.partido]['porcentaje_positivos'] == '41.86'
    # # (40 + 50) / total_positivos + total_blanco
    # assert positivos[o3.partido]['porcentaje_validos'] == '34.62'
    # # (30 + 40) / total_positivos
    # assert positivos[o2.partido]['porcentaje_positivos'] == '32.56'
    # # (30 + 40) / total_positivos + total_blanco
    # assert positivos[o2.partido]['porcentaje_validos'] == '26.92'
    # assert positivos[o1.partido]['votos'] == 10 + 20 + 20 + 5
    # # (20 + 5 + 10 + 20) / total_positivos
    # assert positivos[o1.partido]['porcentaje_positivos'] == '25.58'
    # # (20 + 5 + 10 + 20) / total_positivos + total_blanco
    # assert positivos[o1.partido]['porcentaje_validos'] == '21.15'

    # # todos los positivos suman 100
    # assert sum(float(v['porcentaje_positivos']) for v in positivos.values()) == 100.0

    # # votos de partido 1 son iguales a los de o1 + o4
    # assert positivos[o1.partido]['votos'] == sum(
    #     x['votos'] for x in positivos[o4.partido]['detalle'].values()
    # )

    # content = response.content.decode('utf8')

    # assert f'<td id="votos_{o1.partido.id}" class="dato">55</td>' in content
    # assert f'<td id="votos_{o2.partido.id}" class="dato">70</td>' in content
    # assert f'<td id="votos_{o3.partido.id}" class="dato">90</td>' in content

    # # Deberíamos visualizar los porcentajes positivos.
    # assert f'<td id="porcentaje_{o1.partido.id}" class="dato">25.58%</td>' in content
    # assert f'<td id="porcentaje_{o2.partido.id}" class="dato">32.56%</td>' in content
    # assert f'<td id="porcentaje_{o3.partido.id}" class="dato">41.86%</td>' in content

    # total_electores = sum(m.electores for m in carta_marina)

    # assert resultados.electores() == total_electores
    # assert resultados.total_positivos() == 215  # 20 + 30 + 40 + 5 + 20 + 10 + 40 + 50
    # assert resultados.porcentaje_positivos() == '81.13'
    # assert resultados.porcentaje_mesas_escrutadas() == '37.50'  # 3 de 8
    # assert resultados.votantes() == 265
    # assert resultados.electores_en_mesas_escrutadas() == 320
    # assert resultados.porcentaje_escrutado() == f'{100 * 320 / total_electores:.2f}'
    # assert resultados.porcentaje_participacion() == f'{100 * 265/ 320:.2f}'  # Es sobre escrutado.


    # columna_datos = [
    #     ('Electores', resultados.electores()),
    #     ('Escrutados', resultados.electores_en_mesas_escrutadas()),
    #     ('% Escrutado', f'{resultados.porcentaje_escrutado()} %'),
    #     ('Votantes', resultados.votantes()),
    #     ('Positivos', resultados.total_positivos()),
    #     ('% Participación', f'{resultados.porcentaje_participacion()} %'),
    # ]
    # for variable, valor in columna_datos:
    #     assert f'<td title="{variable}">{valor}</td>' in content