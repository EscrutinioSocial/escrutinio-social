import pytest

from django.urls import reverse

from elecciones.models import (OPCIONES_A_CONSIDERAR, TIPOS_DE_AGREGACIONES, Carga, MesaCategoria, Opcion)

from .factories import CargaFactory
from .test_models import consumir_novedades_y_actualizar_objetos
from .utils import cargar_votos


def test_status_mesas(mesas_con_votos):
    m1, m2, m3, *_ = mesas_con_votos
    categoria = m1.categorias.get()

    assert MesaCategoria.objects.get(mesa=m1, categoria=categoria).status == 'total_sin_consolidar'
    assert MesaCategoria.objects.get(mesa=m2, categoria=categoria).status == 'total_consolidada_csv'
    assert MesaCategoria.objects.get(mesa=m3, categoria=categoria).status == 'total_consolidada_dc'


def test_todas_las_cargas(mesas_con_votos, url_resultados, fiscal_client):
    m1, *_ = mesas_con_votos
    categoria = m1.categorias.all().order_by('id').first()
    o1, *_ = categoria.opciones_actuales()
    blancos = Opcion.blancos()

    # Pide todas las opciones, considera las tres mesas
    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]), {
            'opcionaConsiderar': OPCIONES_A_CONSIDERAR.todas,
            'tipoDeAgregacion': TIPOS_DE_AGREGACIONES.todas_las_cargas
        }
    )

    resultados = response.context['resultados']
    assert resultados.total_mesas_escrutadas() == 3
    assert resultados.tabla_positivos()[o1.partido]['votos'] == 185
    assert resultados.tabla_no_positivos()[blancos.nombre_corto]['votos'] == 60


def test_solo_consolidados(mesas_con_votos, url_resultados, fiscal_client):
    m1, *_ = mesas_con_votos
    categoria = m1.categorias.all().order_by('id').first()
    o1, *_ = categoria.opciones_actuales()
    blancos = Opcion.blancos()

    # Pide opciones consolidadas, descarta m1 que tiene una sola carga web
    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]), {
            'opcionaConsiderar': OPCIONES_A_CONSIDERAR.todas,
            'tipoDeAgregacion': TIPOS_DE_AGREGACIONES.solo_consolidados
        }
    )

    resultados = response.context['resultados']
    assert resultados.total_mesas_escrutadas() == 2
    assert resultados.tabla_positivos()[o1.partido]['votos'] == 135
    assert resultados.tabla_no_positivos()[blancos.nombre_corto]['votos'] == 50


def test_solo_consolidados_doble_carga(mesas_con_votos, url_resultados, fiscal_client):
    m1, *_ = mesas_con_votos
    categoria = m1.categorias.all().order_by('id').first()
    o1, *_ = categoria.opciones_actuales()
    blancos = Opcion.blancos()

    # Pide opciones consolidadas con doble, descarta también la carga csv
    response = fiscal_client.get(
        reverse('resultados-categoria', args=[categoria.id]), {
            'opcionaConsiderar': OPCIONES_A_CONSIDERAR.todas,
            'tipoDeAgregacion': TIPOS_DE_AGREGACIONES.solo_consolidados_doble_carga
        }
    )

    resultados = response.context['resultados']
    assert resultados.total_mesas_escrutadas() == 1
    assert resultados.tabla_positivos()[o1.partido]['votos'] == 75
    assert resultados.tabla_no_positivos()[blancos.nombre_corto]['votos'] == 30


@pytest.fixture()
def mesas_con_votos(carta_marina):
    m1, m2, m3, *_ = carta_marina
    categoria = m1.categorias.all().order_by('id').first()
    o1, *_ = categoria.opciones_actuales()
    blancos = Opcion.blancos()

    c1 = CargaFactory(
        tipo=Carga.TIPOS.total,
        origen=Carga.SOURCES.web,
        mesa_categoria__mesa=m1,
        mesa_categoria__categoria=categoria
    )
    cargar_votos(c1, {o1: 50, blancos: 10})

    c2 = CargaFactory(
        tipo=Carga.TIPOS.total,
        origen=Carga.SOURCES.csv,
        mesa_categoria__mesa=m2,
        mesa_categoria__categoria=categoria
    )
    cargar_votos(c2, {o1: 60, blancos: 20})

    c3 = CargaFactory(
        tipo=Carga.TIPOS.total,
        origen=Carga.SOURCES.web,
        mesa_categoria__mesa=m3,
        mesa_categoria__categoria=categoria
    )
    cargar_votos(c3, {o1: 75, blancos: 30})

    c4 = CargaFactory(
        tipo=Carga.TIPOS.total,
        origen=Carga.SOURCES.web,
        mesa_categoria__mesa=m3,
        mesa_categoria__categoria=categoria
    )
    cargar_votos(c4, {
        o1: 75,
        blancos: 30,
    })

    consumir_novedades_y_actualizar_objetos()
    return [m1, m2, m3]
