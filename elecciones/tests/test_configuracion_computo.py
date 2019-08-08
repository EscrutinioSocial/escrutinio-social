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


def test_configuracion_combinada(db, url_resultados, fiscal_client):
    # Seteamos el modo de elección como PASO; por lo tanto
    # los porcentajes que deberíamos visualizar son los porcentaje_validos
    settings.MODO_ELECCION = settings.ME_OPCION_GEN

    # Asegurar una carta marina con dos distritos extra además del "Distrito único".
    mesas = create_carta_marina(create_distritos=2)

    categoria = Categoria.objects.first()
    for mesa in mesas:
        MesaCategoriaFactory(mesa=mesa, categoria=categoria)

    o1, o2, *_ = categoria.opciones.filter(partido__isnull=False)


    # Cargamos los mismos votos en los tres distritos.
    # for distrito in Distrito.objects.exclude(id=1):  # Excluyo al distrito "único" que se crea siempre.
    for distrito in Distrito.objects.all():
        s1, s2 = distrito.secciones.all()

        # En s1 hacemos una carga doble sobre la misma mesa
        mc1, *_ = MesaCategoria.objects.filter(mesa__lugar_votacion__circuito__seccion=s1)
        c1 = CargaFactory(mesa_categoria=mc1, tipo=Carga.TIPOS.total)
        cargar_votos(c1, {o1: 60, o2: 40})

        c2 = CargaFactory(mesa_categoria=mc1, tipo=Carga.TIPOS.total)
        cargar_votos(c2, {o1: 60, o2: 40})

        # En s2 hacemos dos cargas simples en mesas distintas
        mc2, mc3, *_ = MesaCategoria.objects.filter(mesa__lugar_votacion__circuito__seccion=s1)
        c3 = CargaFactory(mesa_categoria=mc2, tipo=Carga.TIPOS.total)
        cargar_votos(c3, {o1: 20, o2: 60})

        c4 = CargaFactory(mesa_categoria=mc3, tipo=Carga.TIPOS.total)
        cargar_votos(c4, {o1: 20, o2: 60})

    consumir_novedades_y_actualizar_objetos()

    # Crear una configuración de cómputo combinada con estrategias diferentes para cada distrito
    configuracion_combinada = ConfiguracionComputoFactory()
    d1, d2, d3 = Distrito.objects.all()

    # Para el primer distrito consideramos todas las cargas.
    ConfiguracionComputoDistritoFactory(
        configuracion=configuracion_combinada,
        distrito=d1,
        agregacion=TIPOS_DE_AGREGACIONES.todas_las_cargas,
        opciones=OPCIONES_A_CONSIDERAR.todas,
    )

    # Para el segundo distrito consideramos sólo las cargas consolidadas
    ConfiguracionComputoDistritoFactory(
        configuracion=configuracion_combinada,
        distrito=d2,
        agregacion=TIPOS_DE_AGREGACIONES.solo_consolidados_doble_carga,
        opciones=OPCIONES_A_CONSIDERAR.todas,
    )

    # Para el último distrito consideramos todas las cargas, 
    # pero utilizamos una proyección que exige dos mesas por agrupacion circuito
    ConfiguracionComputoDistritoFactory(
        configuracion=configuracion_combinada,
        distrito=d1,
        agregacion=TIPOS_DE_AGREGACIONES.todas_las_cargas,
        opciones=OPCIONES_A_CONSIDERAR.todas,
        proyeccion=tecnica_proyeccion(minimo_mesas=2),
    )


    # response = fiscal_client.get(
    #     url_resultados + f'?opcionaConsiderar={OPCIONES_A_CONSIDERAR.prioritarias}'
    # )
    # resultados = response.context['resultados']

    # positivos = resultados.tabla_positivos()
    # # se ordena de acuerdo al que va ganando
    # assert list(positivos.keys()) == [o3.partido, o2.partido, o1.partido]

    # total_positivos = resultados.total_positivos()
    # total_blancos   = resultados.total_blancos()

    # assert total_positivos == 215  # 20 + 30 + 40 + 5 + 20 + 10 + 40 + 50
    # assert total_blancos   == 45    # 5 + 0

    # # cuentas
    # assert positivos[o3.partido]['votos'] == 40 + 50
    # # (40 + 50) / total_positivos
    # assert positivos[o3.partido]['porcentaje_positivos'] == '41.86'
    # # (40 + 50) / total_positivos + total_blanco
    # assert positivos[o3.partido]['porcentaje_validos'] == '34.62'
    # assert positivos[o2.partido]['votos'] == 30 + 40
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

    # assert resultados.total_blancos() == 45
    # assert resultados.porcentaje_blancos() == '16.98'

    # assert resultados.total_nulos() == 5
    # assert resultados.porcentaje_nulos() == '1.89'

    # assert resultados.total_votos() == 265
    # assert resultados.electores() == 800
    # assert resultados.total_sobres() == 0

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
    assert False