from django.urls import reverse
from elecciones.models import Categoria, Carga, Seccion, Opcion

from .factories import (
    CategoriaFactory,
    SeccionFactory,
    OpcionFactory,
    MesaFactory,
    MesaCategoriaFactory,
    CargaFactory,
)
from .test_models import consumir_novedades_y_actualizar_objetos
from .utils import tecnica_proyeccion, cargar_votos


def test_resultados_proyectados(fiscal_client):
    # se crean 3 secciones electorales
    s1, s2, s3 = SeccionFactory.create_batch(3)
    # s1 1000 votantes    # La matanza! :D
    # s2 400 votantes
    # s3 200 votantes

    # Se crean 8 mesas (5 en s1, 2 en s2 y 1 en s3). Todas tienen 200 electores
    ms1, _, ms3 = (
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

    tecnica = tecnica_proyeccion()

    # simulo que van entraron resultados en las mesas 1 (la primera de la seccion 1)
    # y 3 (la primera de la seccion 3).
    #
    # Resultados de la mesa 1: 120 votos partido 1, 80 para el 2, 0 para el 3 y 0 en blanco
    c1 = CargaFactory(mesa_categoria__mesa=m1, tipo=Carga.TIPOS.parcial, mesa_categoria__categoria=categoria)
    cargar_votos(c1, {
        o1: 120,  # 50% de los votos
        o2: 80,  # 40%
        o3: 0,
        Opcion.blancos(): 0,
        Opcion.total_votos(): 200,
        Opcion.sobres(): 200,
    })
    consumir_novedades_y_actualizar_objetos([m1])

    # Resultados de la mesa 3: 79 votos al partido 1, 121 al partido 2 (cero los demas)
    c2 = CargaFactory(mesa_categoria__mesa=m3, tipo=Carga.TIPOS.parcial, mesa_categoria__categoria=categoria)
    cargar_votos(c2, {
        o1: 79,
        o2: 121,
        o3: 0,
        Opcion.blancos(): 0,
        Opcion.total_votos(): 200,
        Opcion.sobres(): 200,
    })

    consumir_novedades_y_actualizar_objetos([m1, m3])

    # ###################
    # Totales sin proyectar:
    # o1 (partido 1): 120 + 79 = 199 votos
    # o2 (partido 2): 80 + 121 = 201 votos
    # sin proyeccion va ganando o2 por 2 votos
    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        f'?tipoDeAgregacion=todas_las_cargas&opcionaConsiderar=prioritarias'
    )
    positivos = response.context['resultados'].tabla_positivos()

    assert list(positivos.keys()) == [o2.partido, o1.partido, o3.partido, o4.partido]

    # cuentas
    assert positivos[o2.partido]['votos'] == 201
    assert positivos[o1.partido]['votos'] == 199
    assert positivos[o3.partido]['votos'] == 0
    assert positivos[o2.partido]['porcentaje_positivos'] == '50.25'  # 201/400
    assert positivos[o1.partido]['porcentaje_positivos'] == '49.75'  # 199/400
    # no hay proyeccion
    assert 'proyeccion' not in positivos[o1.partido]

    # cuando se proyecta, o1 gana porque va ganando en s1 que es la mas populosa
    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        f'?tipoDeAgregacion=todas_las_cargas&opcionaConsiderar=prioritarias&tecnicaDeProyeccion={tecnica.id}'
    )
    positivos = response.context['resultados'].tabla_positivos()
    assert list(positivos.keys()) == [o1.partido, o2.partido, o3.partido]

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
    assert positivos[o1.partido]['porcentaje_positivos'] == '56.58'
    assert positivos[o2.partido]['porcentaje_positivos'] == '43.42'


def test_resultados_proyectados_simple(carta_marina, fiscal_client):
    s1, s2 = Seccion.objects.all()
    o1, o2 = OpcionFactory.create_batch(2)
    categoria = CategoriaFactory(opciones=[o1, o2])
    tecnica = tecnica_proyeccion()

    mesas = carta_marina
    m1 = mesas[0]
    m2 = mesas[4]
    m3 = mesas[5]
    for mesa in mesas:
        MesaCategoriaFactory(mesa=mesa, categoria=categoria)

    c1 = CargaFactory(mesa_categoria__mesa=m1, tipo=Carga.TIPOS.total, mesa_categoria__categoria=categoria)
    cargar_votos(c1, {o1: 40, o2: 30})

    c2 = CargaFactory(mesa_categoria__mesa=m2, tipo=Carga.TIPOS.total, mesa_categoria__categoria=categoria)
    cargar_votos(c2, {o1: 30, o2: 60})

    c3 = CargaFactory(mesa_categoria__mesa=m3, tipo=Carga.TIPOS.total, mesa_categoria__categoria=categoria)
    cargar_votos(c3, {o1: 30, o2: 60})

    consumir_novedades_y_actualizar_objetos([m1, m2])

    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        f'?tipoDeAgregacion=todas_las_cargas&opcionaConsiderar=todas'
    )

    # Sin proyecciones, tenemos 100 votos para la opción 1 y 150 para la opción 2.
    positivos = response.context['resultados'].tabla_positivos()
    assert positivos[o1.partido]['votos'] == 100
    assert positivos[o2.partido]['votos'] == 150
    assert positivos[o1.partido]['porcentaje_positivos'] == '40.00'  # = 100 / 250
    assert positivos[o2.partido]['porcentaje_positivos'] == '60.00'  # = 150 / 250

    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        f'?tipoDeAgregacion=todas_las_cargas&opcionaConsiderar=todas&tecnicaDeProyeccion={tecnica.id}'
    )

    # En la cuenta anterior, la sección 2 esta sobrerepresentada porque tiene más mesas cargadas.
    # Para proyectar los votos de s1 se multiplican por 4 (porque hay cargada 1 mesa de 4)
    # Los votos de s2 se multiplican por 2.
    positivos = response.context['resultados'].tabla_positivos()
    assert positivos[o1.partido]['votos'] == 280  # = 40 * (4/1) + 60 * (4/2)
    assert positivos[o2.partido]['votos'] == 360  # = 30 * (4/1) + 40 * (4/2)
    assert positivos[o1.partido]['porcentaje_positivos'] == '43.75'  # = 280 / 640
    assert positivos[o2.partido]['porcentaje_positivos'] == '56.25'  # = 360 / 640


def test_proyeccion_con_agrupaciones_no_consideradas(carta_marina, fiscal_client):
    s1, s2 = Seccion.objects.all()
    o1, o2 = OpcionFactory.create_batch(2)
    categoria = CategoriaFactory(opciones=[o1, o2])
    tecnica = tecnica_proyeccion(minimo_mesas=2)

    mesas = carta_marina
    m1 = mesas[0]
    m2 = mesas[4]
    m3 = mesas[5]
    for mesa in mesas:
        MesaCategoriaFactory(mesa=mesa, categoria=categoria)

    # Se carga una mesa de la seccion 1
    c1 = CargaFactory(mesa_categoria__mesa=m1, tipo=Carga.TIPOS.total, mesa_categoria__categoria=categoria)
    cargar_votos(c1, {o1: 40, o2: 30})

    # Y dos mesas de la seccion 2
    c2 = CargaFactory(mesa_categoria__mesa=m2, tipo=Carga.TIPOS.total, mesa_categoria__categoria=categoria)
    cargar_votos(c2, {o1: 30, o2: 60})

    c3 = CargaFactory(mesa_categoria__mesa=m3, tipo=Carga.TIPOS.total, mesa_categoria__categoria=categoria)
    cargar_votos(c3, {o1: 30, o2: 60})

    consumir_novedades_y_actualizar_objetos([m1, m2])

    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]) +
        f'?tipoDeAgregacion=todas_las_cargas&opcionaConsiderar=todas&tecnicaDeProyeccion={tecnica.id}'
    )

    resultados = response.context['resultados']

    # Las mesas de la sección 1 no serán tenidas en cuenta.
    assert resultados.total_mesas_escrutadas() == 2
    assert resultados.porcentaje_mesas_escrutadas() == '25.00'

    positivos = resultados.tabla_positivos()
    assert positivos[o1.partido]['votos'] == 120  # = 30 * (4/2)
    assert positivos[o2.partido]['votos'] == 240  # = 60 * (4/2)
    assert positivos[o1.partido]['porcentaje_positivos'] == '33.33'  # = 280 / 640
    assert positivos[o2.partido]['porcentaje_positivos'] == '66.67'  # = 360 / 640

    agrupaciones_no_consideradas = resultados.resultados['agrupaciones_no_consideradas']
    assert agrupaciones_no_consideradas.count() == 1

    nombre_agrupacion, minimo_mesas, mesas_escrutadas = agrupaciones_no_consideradas.first()
    assert s1.nombre in nombre_agrupacion
    assert minimo_mesas == 2
    assert mesas_escrutadas == 1


