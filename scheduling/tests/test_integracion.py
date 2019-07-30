import pytest

from adjuntos.consolidacion import consolidar_identificaciones
from elecciones.models import (
    MesaCategoria, Carga
)
from elecciones.tests.factories import (
    SeccionFactory, CategoriaFactory, MesaCategoriaFactory, CargaFactory, 
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


def verificar_siguiente_mesacat(mesa, categoria, saltear=0):
    for ix in range(saltear+1):
        mesacat = siguiente_mesa_a_cargar()
    if not (mesacat.mesa == mesa and mesacat.categoria == categoria):
        print(f'verificación siguiente mesacat falla, la mesacat encontrada es:')
        print(f'mesa: {mesacat.mesa}  --  categoria: {mesacat.categoria}  --  orden de carga: {mesacat.orden_de_carga}')
    assert mesacat.mesa == mesa
    assert mesacat.categoria == categoria
    return mesacat


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
    Se verifica la secuencia con la que se asignan mesas considerando dos secciones,
    una standard y una prioritaria, de 100 mesas cada una
    """
    asignar_prioridades_standard(settings)
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    fiscal = nuevo_fiscal()

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

    verificar_siguiente_mesacat(mesas_seccion_standard[0], pv)                    # mesacat 1
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[0], pv)                 # mesacat 2
    verificar_siguiente_mesacat(mesas_seccion_standard[1], pv)                    # mesacat 3
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[1], pv)                 # mesacat 4
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[2], pv)                 # mesacat 5 - orden de carga 2400
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[6], pv, 3)              # mesacat 9 - orden de carga 5600
    verificar_siguiente_mesacat(mesas_seccion_standard[2], pv)                    # mesacat 10 - orden de carga 6000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[8], pv, 1)              # mesacat 12 - orden de carga 7200
    verificar_siguiente_mesacat(mesas_seccion_standard[3], pv)                    # mesacat 13 - orden de carga 8000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[9], pv)                 # mesacat 14 - orden de carga 8000
    verificar_siguiente_mesacat(mesas_seccion_standard[4], pv)                    # mesacat 15 - orden de carga 10000
    verificar_siguiente_mesacat(mesas_seccion_standard[9], pv, 4)                 # mesacat 20 - orden de carga 10000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[10], pv)                # mesacat 21 - orden de carga 44000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[25], pv, 14)            # mesacat 36 - orden de carga 104000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[26], pv)                # mesacat 37 - orden de carga 108000
    verificar_siguiente_mesacat(mesas_seccion_standard[10], pv)                   # mesacat 38 - orden de carga 110000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[27], pv)                # mesacat 39 - orden de carga 112000


def test_secuencia_carga_escenario_complejo_1(db, settings):
    """
    Se verifica la secuencia con la que se asignan mesas considerando 
    - dos secciones, una standard y una moderadamente prioritaria, de 50 mesas cada una
    - dos categorias, una standard y una muy prioritaria
    """
    asignar_prioridades_standard(settings)
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    fiscal = nuevo_fiscal()

    seccion_prioritaria = SeccionFactory(nombre="Barrio marítimo")
    circuito_prioritario = CircuitoFactory(seccion=seccion_prioritaria)
    lugar_votacion_prioritario = LugarVotacionFactory(circuito=circuito_prioritario)
    seccion_standard = SeccionFactory(nombre="Bera centro")
    circuito_standard = CircuitoFactory(seccion=seccion_standard)
    lugar_votacion_standard = LugarVotacionFactory(circuito=circuito_standard)

    pv = CategoriaFactory(nombre="PV")
    dip = CategoriaFactory(nombre="Diputados")
    categorias = [pv, dip]

    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=0,
                               hasta_proporcion=2, prioridad=2)
    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=2,
                               hasta_proporcion=10, prioridad=8)
    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=10,
                               hasta_proporcion=100, prioridad=40)
    PrioridadSchedulingFactory(categoria=pv, desde_proporcion=0, hasta_proporcion=100, prioridad=12)

    mesas_seccion_standard = []
    mesas_seccion_prioritaria = []
    for nro in range(50):
        mesa_standard = MesaFactory(lugar_votacion=lugar_votacion_standard,
                                    numero=str(nro+1), categorias=categorias)
        mesa_prioritaria = MesaFactory(lugar_votacion=lugar_votacion_prioritario,
                                       numero=str(nro+1001), categorias=categorias)
        mesas_seccion_standard.append(mesa_standard)
        mesas_seccion_prioritaria.append(mesa_prioritaria)

    # se identifican las mesas en orden
    for nro in range(50):
        identificar_mesa(mesas_seccion_standard[nro], fiscal)
        identificar_mesa(mesas_seccion_prioritaria[nro], fiscal)

    verificar_siguiente_mesacat(mesas_seccion_standard[0], pv)        # mesacat 1 - orden de carga 24
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[0], pv)     # mesacat 2 - orden de carga 24
    verificar_siguiente_mesacat(mesas_seccion_standard[0], dip)       # mesacat 3 - orden de carga 200
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[0], dip)    # mesacat 4 - orden de carga 200
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[1], pv)     # mesacat 5 - orden de carga 288
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[2], pv)     # mesacat 6 - orden de carga 480
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[3], pv)     # mesacat 7 - orden de carga 672
    verificar_siguiente_mesacat(mesas_seccion_standard[1], pv)        # mesacat 8 - orden de carga 720
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[4], pv)     # mesacat 9 - orden de carga 864
    verificar_siguiente_mesacat(mesas_seccion_standard[2], pv)        # mesacat 10 - orden de carga 1200
    verificar_siguiente_mesacat(mesas_seccion_standard[3], pv)        # mesacat 11 - orden de carga 1680
    verificar_siguiente_mesacat(mesas_seccion_standard[4], pv)        # mesacat 12 - orden de carga 2160
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[1], dip)    # mesacat 13 - orden de carga 2400
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[2], dip)    # mesacat 14 - orden de carga 4000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[5], pv)     # mesacat 15 - orden de carga 5280
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[3], dip)    # mesacat 16 - orden de carga 5600
    verificar_siguiente_mesacat(mesas_seccion_standard[1], dip)       # mesacat 17 - orden de carga 6000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[6], pv)     # mesacat 18 - orden de carga 6240
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[4], dip)    # mesacat 19 - orden de carga 7200
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[7], pv)     # mesacat 20 - orden de carga 7200
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[8], pv)     # mesacat 21 - orden de carga 8160
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[9], pv)     # mesacat 22 - orden de carga 9120
    verificar_siguiente_mesacat(mesas_seccion_standard[2], dip)       # mesacat 23 - orden de carga 10000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[10], pv)    # mesacat 24 - orden de carga 10080
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[13], pv, 2)      # mesacat 27 - orden de carga 12960
    verificar_siguiente_mesacat(mesas_seccion_standard[5], pv)             # mesacat 28 - orden de carga 13200
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[14], pv)         # mesacat 29 - orden de carga 13920
    verificar_siguiente_mesacat(mesas_seccion_standard[3], dip)            # mesacat 30 - orden de carga 10000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[18], pv, 4)      # mesacat 35 - orden de carga 17760
    verificar_siguiente_mesacat(mesas_seccion_standard[4], dip)            # mesacat 36 - orden de carga 18000
    verificar_siguiente_mesacat(mesas_seccion_standard[7], pv)             # mesacat 37 - orden de carga 18000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[5], dip, 37)     # mesacat 75 - orden de carga 44000
    verificar_siguiente_mesacat(mesas_seccion_standard[18], pv)            # mesacat 76 - orden de carga 44400
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[46], pv)         # mesacat 77 - orden de carga 44640
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[49], pv, 3)      # mesacat 81 - orden de carga 47520
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[6], dip, 2)      # mesacat 84 - orden de carga 52000
    verificar_siguiente_mesacat(mesas_seccion_standard[22], pv)            # mesacat 85 - orden de carga 54000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[13], dip, 28)    # mesacat 114 - orden de carga 108000
    verificar_siguiente_mesacat(mesas_seccion_standard[45], pv)            # mesacat 115 - orden de carga 109200
    verificar_siguiente_mesacat(mesas_seccion_standard[5], dip)            # mesacat 116 - orden de carga 110000
    verificar_siguiente_mesacat(mesas_seccion_standard[49], pv, 4)         # mesacat 121 - orden de carga 118800
    verificar_siguiente_mesacat(mesas_seccion_standard[9], dip, 12)        # mesacat 134 - orden de carga 190000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[24], dip)        # mesacat 135 - orden de carga 196000


def test_secuencia_carga_escenario_complejo_2(db, settings):
    """
    Se verifica la secuencia con la que se asignan mesas considerando 
    - dos secciones, una standard y una muy prioritaria, de 50 mesas cada una
    - dos categorias, una standard y una moderadamente prioritaria
    """
    asignar_prioridades_standard(settings)
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    fiscal = nuevo_fiscal()

    seccion_prioritaria = SeccionFactory(nombre="Barrio marítimo")
    circuito_prioritario = CircuitoFactory(seccion=seccion_prioritaria)
    lugar_votacion_prioritario = LugarVotacionFactory(circuito=circuito_prioritario)
    seccion_standard = SeccionFactory(nombre="Bera centro")
    circuito_standard = CircuitoFactory(seccion=seccion_standard)
    lugar_votacion_standard = LugarVotacionFactory(circuito=circuito_standard)

    pv = CategoriaFactory(nombre="PV")
    dip = CategoriaFactory(nombre="Diputados")
    categorias = [pv, dip]

    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=0,
                               hasta_proporcion=2, prioridad=2)
    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=2,
                               hasta_proporcion=10, prioridad=5)
    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=10,
                               hasta_proporcion=100, prioridad=25)
    PrioridadSchedulingFactory(categoria=pv, desde_proporcion=0, hasta_proporcion=100, prioridad=30)

    mesas_seccion_standard = []
    mesas_seccion_prioritaria = []
    for nro in range(50):
        mesa_standard = MesaFactory(lugar_votacion=lugar_votacion_standard,
                                    numero=str(nro+1), categorias=categorias)
        mesa_prioritaria = MesaFactory(lugar_votacion=lugar_votacion_prioritario,
                                       numero=str(nro+1001), categorias=categorias)
        mesas_seccion_standard.append(mesa_standard)
        mesas_seccion_prioritaria.append(mesa_prioritaria)

    # se identifican las mesas en orden
    for nro in range(50):
        identificar_mesa(mesas_seccion_standard[nro], fiscal)
        identificar_mesa(mesas_seccion_prioritaria[nro], fiscal)

    verificar_siguiente_mesacat(mesas_seccion_standard[0], pv)        # mesacat 1 - orden de carga 60
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[0], pv)     # mesacat 2 - orden de carga 24
    verificar_siguiente_mesacat(mesas_seccion_standard[0], dip)       # mesacat 3 - orden de carga 200
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[0], dip)    # mesacat 4 - orden de carga 200
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[1], pv)     # mesacat 5 - orden de carga 450
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[2], pv)     # mesacat 6 - orden de carga 750
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[3], pv)     # mesacat 7 - orden de carga 1050
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[4], pv)     # mesacat 8 - orden de carga 1350
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[1], dip)    # mesacat 9 - orden de carga 1500
    verificar_siguiente_mesacat(mesas_seccion_standard[1], pv)        # mesacat 10 - orden de carga 1800
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[2], dip)    # mesacat 11 - orden de carga 2500
    verificar_siguiente_mesacat(mesas_seccion_standard[2], pv)        # mesacat 12 - orden de carga 3000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[3], dip)    # mesacat 13 - orden de carga 3500
    verificar_siguiente_mesacat(mesas_seccion_standard[3], pv)        # mesacat 14 - orden de carga 4200
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[4], dip)    # mesacat 15 - orden de carga 4500
    verificar_siguiente_mesacat(mesas_seccion_standard[4], pv)        # mesacat 16 - orden de carga 5400
    verificar_siguiente_mesacat(mesas_seccion_standard[1], dip)       # mesacat 17 - orden de carga 6000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[11], pv, 8)       # mesacat 26 - orden de carga 17250
    verificar_siguiente_mesacat(mesas_seccion_standard[4], dip)             # mesacat 27 - orden de carga 18000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[5], dip, 6)       # mesacat 34 - orden de carga 27500
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[6], dip, 4)       # mesacat 39 - orden de carga 32500
    verificar_siguiente_mesacat(mesas_seccion_standard[5], pv)              # mesacat 40 - orden de carga 33000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[22], pv)          # mesacat 41 - orden de carga 33750
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[14], dip, 38)     # mesacat 80 - orden de carga 72500
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[48], pv)          # mesacat 81 - orden de carga 72750
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[49], pv)          # mesacat 82 - orden de carga 74250
    verificar_siguiente_mesacat(mesas_seccion_standard[12], pv)             # mesacat 83 - orden de carga 75000


def test_secuencia_carga_seccion_con_corte(db, settings):
    """
    Se verifica la secuencia con la que se asignan mesas considerando 
    - tres secciones: una standard, una prioritaria, una con corte a las 7 mesas, de 50 mesas cada una
    - una categoria standard
    """
    asignar_prioridades_standard(settings)
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    fiscal = nuevo_fiscal()

    seccion_prioritaria = SeccionFactory(nombre="Barrio marítimo")
    circuito_prioritario = CircuitoFactory(seccion=seccion_prioritaria)
    lugar_votacion_prioritario = LugarVotacionFactory(circuito=circuito_prioritario)
    seccion_standard = SeccionFactory(nombre="Bera centro")
    circuito_standard = CircuitoFactory(seccion=seccion_standard)
    lugar_votacion_standard = LugarVotacionFactory(circuito=circuito_standard)
    seccion_corte = SeccionFactory(nombre="Solano")
    circuito_corte = CircuitoFactory(seccion=seccion_corte)
    lugar_votacion_corte = LugarVotacionFactory(circuito=circuito_corte)

    pv = CategoriaFactory(nombre="PV")
    categorias = [pv]

    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=0,
                               hasta_proporcion=2, prioridad=2)
    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=2,
                               hasta_proporcion=10, prioridad=8)
    PrioridadSchedulingFactory(seccion=seccion_prioritaria, desde_proporcion=10,
                               hasta_proporcion=100, prioridad=40)
    PrioridadSchedulingFactory(seccion=seccion_corte, desde_proporcion=0,
                               hasta_proporcion=2, prioridad=2, hasta_cantidad=7)

    mesas_seccion_standard = []
    mesas_seccion_prioritaria = []
    mesas_seccion_corte = []
    for nro in range(50):
        mesa_standard = MesaFactory(lugar_votacion=lugar_votacion_standard,
                                    numero=str(nro), categorias=categorias)
        mesa_prioritaria = MesaFactory(lugar_votacion=lugar_votacion_prioritario,
                                       numero=str(nro+1000), categorias=categorias)
        mesa_corte = MesaFactory(lugar_votacion=lugar_votacion_corte,
                                       numero=str(nro+2000), categorias=categorias)
        mesas_seccion_standard.append(mesa_standard)
        mesas_seccion_prioritaria.append(mesa_prioritaria)
        mesas_seccion_corte.append(mesa_corte)

    # se identifican las mesas en orden
    for nro in range(50):
        identificar_mesa(mesas_seccion_standard[nro], fiscal)
        identificar_mesa(mesas_seccion_prioritaria[nro], fiscal)
        identificar_mesa(mesas_seccion_corte[nro], fiscal)

    verificar_siguiente_mesacat(mesas_seccion_standard[0], pv)        # mesacat 1 - orden de carga 200
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[0], pv)     # mesacat 2 - orden de carga 200
    verificar_siguiente_mesacat(mesas_seccion_corte[0], pv)           # mesacat 3 - orden de carga 200
    verificar_siguiente_mesacat(mesas_seccion_corte[1], pv)           # mesacat 4 - orden de carga 600
    verificar_siguiente_mesacat(mesas_seccion_corte[2], pv)           # mesacat 5 - orden de carga 1000
    verificar_siguiente_mesacat(mesas_seccion_corte[3], pv)           # mesacat 6 - orden de carga 1400
    verificar_siguiente_mesacat(mesas_seccion_corte[4], pv)           # mesacat 7 - orden de carga 1800
    verificar_siguiente_mesacat(mesas_seccion_corte[5], pv)           # mesacat 8 - orden de carga 2200
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[1], pv)     # mesacat 9 - orden de carga 2400
    verificar_siguiente_mesacat(mesas_seccion_corte[6], pv)           # mesacat 10 - orden de carga 2600
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[2], pv)     # mesacat 11 - orden de carga 4000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[3], pv)     # mesacat 12 - orden de carga 5600
    verificar_siguiente_mesacat(mesas_seccion_standard[1], pv)        # mesacat 13 - orden de carga 6000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[4], pv)     # mesacat 14 - orden de carga 7200
    verificar_siguiente_mesacat(mesas_seccion_standard[2], pv)        # mesacat 15 - orden de carga 10000
    verificar_siguiente_mesacat(mesas_seccion_standard[3], pv)        # mesacat 16 - orden de carga 14000
    verificar_siguiente_mesacat(mesas_seccion_standard[4], pv)        # mesacat 17 - orden de carga 18000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[5], pv)     # mesacat 18 - orden de carga 44000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[6], pv)     # mesacat 19 - orden de carga 52000
    verificar_siguiente_mesacat(mesas_seccion_standard[5], pv, 7)           # mesacat 27 - orden de carga 110000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[14], pv)          # mesacat 28 - orden de carga 116000
    verificar_siguiente_mesacat(mesas_seccion_standard[7], pv, 5)           # mesacat 34 - orden de carga 150000
    verificar_siguiente_mesacat(mesas_seccion_corte[7], pv)                 # mesacat 35 - orden de carga 150000
    # ... y a partir de este punto, las mesas de standard y corte se cargan parejo
    verificar_siguiente_mesacat(mesas_seccion_standard[14], pv, 29)         # mesacat 65 - orden de carga 290000
    verificar_siguiente_mesacat(mesas_seccion_corte[14], pv)                # mesacat 66 - orden de carga 290000
    verificar_siguiente_mesacat(mesas_seccion_prioritaria[36], pv)          # mesacat 67 - orden de carga 292000


def test_excluir_fiscal_que_ya_cargo(db, settings):
    """
    Se verifica que no se propone una MesaCategoria para cargar, a un fiscal que ya hizo una carga
    sobre esa MesaCategoria.
    """
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    settings.MIN_COINCIDENCIAS_CARGAS = 2
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    pv = CategoriaFactory(nombre="PV")
    gv = CategoriaFactory(nombre="GV")
    # hago que la categoria pv sea prioritaria
    PrioridadSchedulingFactory(categoria=pv, desde_proporcion=0, hasta_proporcion=100, prioridad=30)

    mesa = MesaFactory(numero="51", categorias=[gv, pv])
    identificar_mesa(mesa, fiscal_3)
    mesacat_pv = MesaCategoria.objects.filter(mesa=mesa, categoria=pv).first()
    mesacat_gv = MesaCategoria.objects.filter(mesa=mesa, categoria=gv).first()

    # antes de cargar, la siguiente mesacat para ambos fiscales es pv, que es más prioritaria
    mesacat_fiscal_2 = MesaCategoria.objects.con_carga_pendiente().sin_cargas_del_fiscal(fiscal_2).mas_prioritaria()
    mesacat_fiscal_3 = MesaCategoria.objects.con_carga_pendiente().sin_cargas_del_fiscal(fiscal_3).mas_prioritaria()
    assert mesacat_fiscal_2 == mesacat_pv
    assert mesacat_fiscal_3 == mesacat_pv

    # agrego una carga 
    carga = CargaFactory(mesa_categoria=mesacat_pv, fiscal=fiscal_2, tipo=Carga.TIPOS.parcial)

    # la siguiente mesacat para el fiscal_2 es gv, porque de pv ya hizo una carga
    # la del fiscal 3 es pv, que es más prioritaria
    mesacat_fiscal_2 = MesaCategoria.objects.con_carga_pendiente().sin_cargas_del_fiscal(fiscal_2).mas_prioritaria()
    mesacat_fiscal_3 = MesaCategoria.objects.con_carga_pendiente().sin_cargas_del_fiscal(fiscal_3).mas_prioritaria()
    assert mesacat_fiscal_2 == mesacat_gv
    assert mesacat_fiscal_3 == mesacat_pv

    # el fiscal 2 carga la mesacat que le queda
    carga = CargaFactory(mesa_categoria=mesacat_gv, fiscal=fiscal_2, tipo=Carga.TIPOS.parcial)

    # ahora el fiscal 2 no tiene mesacat para cargar, el fiscal 3 sigue con pv como prioritaria
    mesacat_fiscal_2 = MesaCategoria.objects.con_carga_pendiente().sin_cargas_del_fiscal(fiscal_2).mas_prioritaria()
    mesacat_fiscal_3 = MesaCategoria.objects.con_carga_pendiente().sin_cargas_del_fiscal(fiscal_3).mas_prioritaria()
    assert mesacat_fiscal_2 == None
    assert mesacat_fiscal_3 == mesacat_pv
