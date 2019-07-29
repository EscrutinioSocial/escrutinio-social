import pytest

from adjuntos.consolidacion import consolidar_identificaciones
from elecciones.models import (
    MesaCategoria
)
from elecciones.tests.factories import (
    SeccionFactory, CategoriaFactory, MesaCategoriaFactory,
    CircuitoFactory, LugarVotacionFactory, MesaFactory, 
    IdentificacionFactory, AttachmentFactory,
    UserFactory, FiscalFactory
)
from .factories import PrioridadSchedulingFactory
from .utils_para_test import asignar_prioridades_standard


def nuevo_fiscal():
    usuario = UserFactory()
    fiscal = FiscalFactory(user=usuario)
    return fiscal


def identificar(attach, mesa, fiscal):
    return IdentificacionFactory(
        status='identificada',
        attachment=attach,
        mesa=mesa,
        fiscal=fiscal
    )

def identificar_mesa(mesa, fiscal):
    attach = AttachmentFactory()
    identificar(attach, mesa, fiscal)
    consolidar_identificaciones(attach)


def verificar_valores_scheduling_mesacat(mesa, cat, percentil, orden_de_llegada, orden_de_carga):
    mesacat = MesaCategoria.objects.filter(mesa=mesa, categoria=cat)[0]
    assert mesacat.percentil == percentil
    assert mesacat.orden_de_llegada == orden_de_llegada
    assert mesacat.orden_de_carga == orden_de_carga


def test_orden_de_carga_escenario_base(db, settings):
    """
    Se verifica la asignacion de ordenes de carga para una seccion standard, con dos categorias standard
    con una categoria prioritaria y una standard
    """
    asignar_prioridades_standard(settings)
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    fiscal = nuevo_fiscal()

    # una seccion standard, un circuito, 25 mesas en el mismo lugar de votacion, dos categorias standard
    la_seccion = SeccionFactory(nombre="Bera centro")
    circuito = CircuitoFactory(seccion=la_seccion)
    lugar_votacion = LugarVotacionFactory(circuito=circuito)

    pv = CategoriaFactory(nombre="PV")
    gv = CategoriaFactory(nombre="GV")
    categorias = [pv, gv]

    mesas = []
    for nro in range(25):
        mesa = MesaFactory(lugar_votacion=lugar_votacion, numero=str(nro))
        mesas.append(mesa)
        for cat in categorias:
            MesaCategoriaFactory(mesa=mesa, categoria=cat)

    # primera mesa
    identificar_mesa(mesas[0], fiscal)
    verificar_valores_scheduling_mesacat(mesas[0], pv, 1, 1, 200)
    verificar_valores_scheduling_mesacat(mesas[0], gv, 1, 1, 200)

    # segunda mesa
    identificar_mesa(mesas[1], fiscal)
    verificar_valores_scheduling_mesacat(mesas[1], pv, 5, 2, 10000)
    verificar_valores_scheduling_mesacat(mesas[1], gv, 5, 2, 10000)

    # quinta mesa
    for nro in range(2, 5):
        identificar_mesa(mesas[nro], fiscal)
    verificar_valores_scheduling_mesacat(mesas[4], pv, 17, 5, 170000)
    verificar_valores_scheduling_mesacat(mesas[4], gv, 17, 5, 170000)

    # mesa 25
    for nro in range(5, 25):
        identificar_mesa(mesas[nro], fiscal)
    verificar_valores_scheduling_mesacat(mesas[24], pv, 97, 25, 970000)
    verificar_valores_scheduling_mesacat(mesas[24], gv, 97, 25, 970000)



def test_orden_de_carga_seccion_categoria_prioritaria(db, settings):
    """
    Se verifica la asignacion de ordenes de carga para una seccion prioritaria, 
    con una categoria prioritaria y una standard
    """
    asignar_prioridades_standard(settings)
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    fiscal = nuevo_fiscal()

    # una seccion prioritaria, un circuito, 200 mesas en el mismo lugar de votacion, una categoria prioritaria, una standard
    la_seccion = SeccionFactory(nombre="Bera centro")
    circuito = CircuitoFactory(seccion=la_seccion)
    lugar_votacion = LugarVotacionFactory(circuito=circuito)

    pv = CategoriaFactory(nombre="PV")
    gv = CategoriaFactory(nombre="GV")
    categorias = [pv, gv]

    PrioridadSchedulingFactory(seccion=la_seccion, desde_proporcion=0, hasta_proporcion=2, prioridad=1)
    PrioridadSchedulingFactory(seccion=la_seccion, desde_proporcion=2, hasta_proporcion=10, prioridad=5)
    PrioridadSchedulingFactory(seccion=la_seccion, desde_proporcion=10, hasta_proporcion=100, prioridad=40)
    PrioridadSchedulingFactory(categoria=pv, desde_proporcion=0, hasta_proporcion=100, prioridad=20)

    mesas = []
    for nro in range(200):
        mesa = MesaFactory(lugar_votacion=lugar_votacion, numero=str(nro))
        mesas.append(mesa)
        for cat in categorias:
            MesaCategoriaFactory(mesa=mesa, categoria=cat)
    
    # primera mesa
    identificar_mesa(mesas[0], fiscal)
    verificar_valores_scheduling_mesacat(mesas[0], pv, 1, 1, 20)
    verificar_valores_scheduling_mesacat(mesas[0], gv, 1, 1, 100)

    # segunda mesa
    identificar_mesa(mesas[1], fiscal)
    verificar_valores_scheduling_mesacat(mesas[1], pv, 1, 2, 20)
    verificar_valores_scheduling_mesacat(mesas[1], gv, 1, 2, 100)

    # tercera mesa
    identificar_mesa(mesas[2], fiscal)
    verificar_valores_scheduling_mesacat(mesas[2], pv, 2, 3, 40)
    verificar_valores_scheduling_mesacat(mesas[2], gv, 2, 3, 200)

    # quinta mesa
    identificar_mesa(mesas[3], fiscal)
    identificar_mesa(mesas[4], fiscal)
    verificar_valores_scheduling_mesacat(mesas[4], pv, 3, 5, 300)
    verificar_valores_scheduling_mesacat(mesas[4], gv, 3, 5, 1500)

    # mesa 19
    for nro in range(5,19):
        identificar_mesa(mesas[nro], fiscal)
    verificar_valores_scheduling_mesacat(mesas[18], pv, 10, 19, 1000)
    verificar_valores_scheduling_mesacat(mesas[18], gv, 10, 19, 5000)

    # mesa 20
    identificar_mesa(mesas[19], fiscal)
    verificar_valores_scheduling_mesacat(mesas[19], pv, 10, 20, 1000)
    verificar_valores_scheduling_mesacat(mesas[19], gv, 10, 20, 5000)

    # mesa 21
    identificar_mesa(mesas[20], fiscal)
    verificar_valores_scheduling_mesacat(mesas[20], pv, 11, 21, 8800)
    verificar_valores_scheduling_mesacat(mesas[20], gv, 11, 21, 44000)

    # mesa 51
    for nro in range(21, 51):
        identificar_mesa(mesas[nro], fiscal)
    verificar_valores_scheduling_mesacat(mesas[50], pv, 26, 51, 800 * 26)
    verificar_valores_scheduling_mesacat(mesas[50], gv, 26, 51, 4000 * 26)


def test_orden_de_carga_cantidad_mesas_prioritarias(db, settings):
    """
    Se verifica la asignacion de ordenes de carga para una seccion en la que se establece un minimo de mesas
    con maxima prioridad; con una categoria standard
    """
    asignar_prioridades_standard(settings)
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    fiscal = nuevo_fiscal()

    # una seccion standard, un circuito, 30 mesas en el mismo lugar de votacion, dos categorias standard
    la_seccion = SeccionFactory(nombre="Bera centro")
    circuito = CircuitoFactory(seccion=la_seccion)
    lugar_votacion = LugarVotacionFactory(circuito=circuito)
    pv = CategoriaFactory(nombre="PV")
    categorias = [pv]

    PrioridadSchedulingFactory(seccion=la_seccion, desde_proporcion=0, hasta_proporcion=2, prioridad=2, hasta_cantidad=7)

    mesas = []
    for nro in range(30):
        mesa = MesaFactory(lugar_votacion=lugar_votacion, numero=str(nro))
        mesas.append(mesa)
        for cat in categorias:
            MesaCategoriaFactory(mesa=mesa, categoria=cat)

    # primera mesa
    identificar_mesa(mesas[0], fiscal)
    verificar_valores_scheduling_mesacat(mesas[0], pv, 1, 1, 200)

    # segunda mesa
    identificar_mesa(mesas[1], fiscal)
    verificar_valores_scheduling_mesacat(mesas[1], pv, 4, 2, 800)

    # sexta mesa
    for nro in range(2, 6):
        identificar_mesa(mesas[nro], fiscal)
    verificar_valores_scheduling_mesacat(mesas[5], pv, 17, 6, 3400)

    # mesa 7
    identificar_mesa(mesas[6], fiscal)
    verificar_valores_scheduling_mesacat(mesas[6], pv, 21, 7, 4200)

    # mesa 8
    identificar_mesa(mesas[7], fiscal)
    verificar_valores_scheduling_mesacat(mesas[7], pv, 24, 8, 240000)

    # mesa 20
    for nro in range(5, 20):
        identificar_mesa(mesas[nro], fiscal)
    verificar_valores_scheduling_mesacat(mesas[19], pv, 64, 20, 640000)
