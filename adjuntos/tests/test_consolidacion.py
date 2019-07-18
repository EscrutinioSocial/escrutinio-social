import string
import pytest
from elecciones.tests.factories import (
    AttachmentFactory,
    MesaCategoriaFactory,
    CategoriaFactory,
    IdentificacionFactory,
    CircuitoFactory,
    MesaFactory
)
from elecciones.models import MesaCategoria, Categoria


def test_identificacion_consolidada_calcula_orden_de_prioridad(db):
    mc1 = MesaCategoriaFactory()
    mesa = mc1.mesa
    mc2 = MesaCategoriaFactory(mesa=mesa)
    assert mc1.orden_de_carga is None
    assert mc2.orden_de_carga is None

    # emulo consolidacion
    i = IdentificacionFactory(status='identificada', mesa=mc1.mesa)
    AttachmentFactory(status='identificada', mesa=mesa, identificacion_testigo=i)
    mc1.refresh_from_db()
    mc2.refresh_from_db()
    assert mc1.orden_de_carga is not None
    assert mc2.orden_de_carga is not None


def test_siguiente_prioriza_estado_y_luego_coeficiente(db, django_assert_num_queries):
    c = CategoriaFactory(prioridad=1)
    mc1 = MesaCategoriaFactory(
        status=MesaCategoria.STATUS.parcial_sin_consolidar,
        categoria=c,
        orden_de_carga=1.0
    )
    mc2 = MesaCategoriaFactory(
        categoria=c,
        status=MesaCategoria.STATUS.total_en_conflicto,
        orden_de_carga=99.0
    )
    mc3 = MesaCategoriaFactory(
        categoria=c,
        status=MesaCategoria.STATUS.total_en_conflicto,
        orden_de_carga=2.0
    )
    with django_assert_num_queries(1):
        assert MesaCategoria.objects.siguiente() == mc1
    mc1.take()
    assert MesaCategoria.objects.siguiente() == mc3
    mc3.take()
    assert MesaCategoria.objects.siguiente() == mc2
    mc2.take()
    assert MesaCategoria.objects.siguiente() is None


@pytest.mark.parametrize('prioridades, expected', [
    # si las categorias tienen la misma prioridad
    # el orden para igual circuito es equitativo
    ([0, 0], 'abababababababababab'),
    ([1, 1], 'abababababababababab'),
    # si "a" tiene el doble de prioridad que "b"
    # va a tender a tener prioridad
    ([1, 2], 'ababaabaababaababbbb'),
    # con mas diferencia de prioridad, mas sesgo en favor de "a"
    ([1, 3], 'abaabaabaaabaabbbbbb'),
    # ahora 3 categorias, dos de las cuales tienen igual prioridad
    # se favorece la 'a', mientras 'b' y 'c' se intercalan
    ([1, 2, 2], 'abcabcaabcaabcabcaabcabcbcbcbc'),
])
def test_prioridad_de_categoria_influye_en_orden(db, prioridades, expected):
    """
    dado un circuito con 10 mesas y N categorias llamadas 'a', 'b', ...
    con prioridades dadas por ``prioridades`` respectivamente,
    el coeficiente de orden queda influenciado unicamente por la proopridad
    de la categoria.
    """
    circuito = CircuitoFactory()
    categorias = []
    for i, prioridad in enumerate(prioridades):
        # las categorias se llaman "a", "b", etc.
        categorias.append(
            CategoriaFactory(prioridad=prioridad, nombre=string.ascii_letters[i])
        )
    mesas = MesaFactory.create_batch(
        10,
        categorias=categorias,
        circuito=circuito
    )
    # calculo todos los ordenes de carga
    mcs = MesaCategoria.objects.filter(mesa__in=mesas).defer('orden_de_carga').distinct()
    for mc in mcs:
        mc.actualizar_orden_de_carga()
    result = mcs.order_by('orden_de_carga').values_list('categoria__nombre', flat=True)
    assert ''.join(result) == expected


@pytest.mark.parametrize('consolidadas, expected', [
    # faltan todas.
    # ([0, 0], 'abababababababababab'),
    # "b" tiene el 40%
    #([0, 4], 'abababababababaaa'),
    # ([5, 9], 'ababaaa'),   # FIX ME . por qué hay 2 "b" si hay 9 de 10 ya consolidadas?
    ([6, 1, 0], 'abcabcabcabcabcbcbcbcbcc'),
])
def test_proporcion_de_consolidadas_influye(db, consolidadas, expected):

    circuito = CircuitoFactory()
    categorias = []
    for i, consolidadas_cat in enumerate(consolidadas):
        # las categorias se llaman "a", "b", etc.
        cat = CategoriaFactory(prioridad=1, nombre=string.ascii_letters[i])
        MesaCategoriaFactory.create_batch(
            10 - consolidadas_cat,
            categoria=cat,
            mesa__circuito=circuito,
        )
        MesaCategoriaFactory.create_batch(
            consolidadas_cat,
            status=MesaCategoria.STATUS.total_consolidada_dc,
            categoria=cat,
            mesa__circuito=circuito,
        )
        categorias.append(cat.id)

    # el factory de mesas implicitamente crea una mesa categoria
    Categoria.objects.exclude(id__in=categorias).delete()
    assert Categoria.objects.count() == len(consolidadas)

    mcs = MesaCategoria.objects.filter(mesa__circuito=circuito).defer('orden_de_carga').distinct()
    for mc in mcs:
        mc.actualizar_orden_de_carga()

    result = mcs.order_by('orden_de_carga').values_list('categoria__nombre', flat=True)
    assert ''.join(result) == expected
