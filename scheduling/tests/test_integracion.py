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
        mesa = MesaFactory(lugar_votacion=lugar_votacion, numero=str(nro), categorias=categorias)
        mesas.append(mesa)

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
        mesa = MesaFactory(lugar_votacion=lugar_votacion, numero=str(nro), categorias=categorias)
        mesas.append(mesa)
    
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
        mesa = MesaFactory(lugar_votacion=lugar_votacion, numero=str(nro), categorias=categorias)
        mesas.append(mesa)

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


def siguiente_mesa_a_cargar():
    mesacat = MesaCategoria.objects.siguiente()
    mesacat.status = MesaCategoria.STATUS.total_consolidada_dc
    mesacat.save(update_fields=['status'])
    return mesacat


def test_secuencia_carga_secciones_standard_prioritaria(db, settings):
    """
    Se verifica la secuencia con la que se asignan mesas considerando dos secciones de 100 mesas,
    una standard y una prioritaria, de 100 mesas cada una
    """
    asignar_prioridades_standard(settings)
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    fiscal = nuevo_fiscal()

    # una seccion prioritaria y una standard, un circuito, 200 mesas en el mismo lugar de votacion, una categoria prioritaria, una standard
    seccion_prioritaria = SeccionFactory(nombre="Barrio marítimo")
    circuito_prioritario = CircuitoFactory(seccion=seccion_prioritaria)
    lugar_votacion_prioritario = LugarVotacionFactory(circuito=circuito_prioritario)
    seccion_standard = SeccionFactory(nombre="Bera centro")
    circuito_standard = CircuitoFactory(seccion=seccion_standard)
    lugar_votacion_standard = LugarVotacionFactory(circuito=circuito_standard)

    pv = CategoriaFactory(nombre="PV")
    categorias = [pv]

    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=0, hasta_proporcion=2, prioridad=2)
    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=2, hasta_proporcion=10, prioridad=8)
    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=10, hasta_proporcion=100, prioridad=40)

    mesas_seccion_standard = []
    mesas_seccion_prioritaria = []
    for nro in range(100):
        mesa_standard = MesaFactory(lugar_votacion=lugar_votacion_standard, numero=str(nro+1), categorias=categorias)
        mesa_prioritaria = MesaFactory(lugar_votacion=lugar_votacion_prioritario,
                                       numero=str(nro+1001), categorias=categorias)
        mesas_seccion_standard.append(mesa_standard)
        mesas_seccion_prioritaria.append(mesa_prioritaria)

    # se identifican las mesas en orden
    for nro in range(100):
        identificar_mesa(mesas_seccion_standard[nro], fiscal)
        identificar_mesa(mesas_seccion_prioritaria[nro], fiscal)

    # primer mesa a cargar
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_standard[0], categoria=pv)[0]

    # segunda mesa a cargar
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_prioritaria[0], categoria=pv)[0]

    # tercera mesa a cargar
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_standard[1], categoria=pv)[0]

    # cuarta mesa a cargar
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_prioritaria[1], categoria=pv)[0]

    # quinta mesa a cargar - orden_de_carga 2400
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_prioritaria[2], categoria=pv)[0]

    # novena mesa a cargar - orden_de_carga 5600
    for nro in range(4):
        mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_prioritaria[6], categoria=pv)[0]

    # mesa 10 a cargar - orden_de_carga 6000
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_standard[2], categoria=pv)[0]

    # mesa 12 a cargar - orden_de_carga 7200
    mesacat = siguiente_mesa_a_cargar()
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_prioritaria[8], categoria=pv)[0]

    # mesa 13 a cargar - orden_de_carga 8000
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_standard[3], categoria=pv)[0]

    # mesa 14 a cargar - orden_de_carga 8000
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_prioritaria[9], categoria=pv)[0]

    # mesa 15 a cargar - orden_de_carga 10000
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_standard[4], categoria=pv)[0]

    # mesa 20 a cargar - orden_de_carga 20000
    for nro in range(5):
        mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_standard[9], categoria=pv)[0]

    # mesa 21 a cargar - orden_de_carga 44000
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_prioritaria[10], categoria=pv)[0]

    # mesa 36 a cargar - orden_de_carga 104000
    for nro in range(15):
        mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_prioritaria[25], categoria=pv)[0]

    # mesa 37 a cargar - orden_de_carga 108000
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_prioritaria[26], categoria=pv)[0]

    # mesa 38 a cargar - orden_de_carga 110000
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_standard[10], categoria=pv)[0]

    # mesa 39 a cargar - orden_de_carga 112000
    mesacat = siguiente_mesa_a_cargar()
    assert mesacat == MesaCategoria.objects.filter(mesa=mesas_seccion_prioritaria[27], categoria=pv)[0]
