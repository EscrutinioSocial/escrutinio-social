import pytest

from elecciones.tests.factories import (
    SeccionFactory, CategoriaFactory
)
from scheduling.models import PrioridadScheduling
from .utils_para_test import (
    asignar_prioridades_standard, crear_mesas, crear_seccion, nuevo_fiscal, identificar_mesa,
    verificar_valores_scheduling_mesacat, verificar_siguiente_mesacat
)


def test_configuracion_categoria(db):
    categoria=CategoriaFactory(prioridad=15)
    prioridades = PrioridadScheduling.objects.filter(categoria=categoria)
    assert prioridades.count() == 1 
    assert prioridades.first().prioridad == 15
    categoria.prioridad = 21
    categoria.save(update_fields=['prioridad'])
    prioridades = PrioridadScheduling.objects.filter(categoria=categoria)
    assert prioridades.count() == 1
    assert prioridades.first().prioridad == 21
    categoria.prioridad = None
    categoria.save(update_fields=['prioridad'])
    prioridades = PrioridadScheduling.objects.filter(categoria=categoria)
    assert prioridades.count() == 0

    categoria_2 = CategoriaFactory()
    prioridades = PrioridadScheduling.objects.filter(categoria=categoria)
    assert prioridades.count() == 0


def test_configuracion_seccion(db):
    seccion = SeccionFactory(prioridad_hasta_2=1, prioridad_2_a_10=12)
    seccion_2 = SeccionFactory()
    prioridades = PrioridadScheduling.objects.filter(seccion=seccion)
    assert prioridades.count() == 2
    assert prioridades.filter(desde_proporcion=0).first().prioridad == 1
    assert prioridades.filter(desde_proporcion=0).first().hasta_cantidad is None
    assert prioridades.filter(desde_proporcion=2).first().prioridad == 12
    assert prioridades.filter(desde_proporcion=2).first().hasta_proporcion == 10
    prioridades = PrioridadScheduling.objects.filter(seccion=seccion_2)
    assert prioridades.count() == 0

    seccion.prioridad_hasta_2 = None
    seccion.prioridad_2_a_10 = 15
    seccion.prioridad_10_a_100 = 45
    seccion.save(update_fields=['prioridad_hasta_2', 'prioridad_2_a_10', 'prioridad_10_a_100'])
    prioridades = PrioridadScheduling.objects.filter(seccion=seccion)
    assert prioridades.count() == 2
    assert prioridades.filter(desde_proporcion=2).first().prioridad == 15
    assert prioridades.filter(desde_proporcion=10).first().prioridad == 45
    assert prioridades.filter(desde_proporcion=10).first().hasta_proporcion == 100

    seccion.prioridad_hasta_2 = 3
    seccion.cantidad_minima_prioridad_hasta_2 = 7
    seccion.save(update_fields=['prioridad_hasta_2', 'cantidad_minima_prioridad_hasta_2'])
    prioridades = PrioridadScheduling.objects.filter(seccion=seccion)
    assert prioridades.count() == 3
    assert prioridades.filter(desde_proporcion=0).first().prioridad == 3
    assert prioridades.filter(desde_proporcion=0).first().hasta_cantidad == 7
    assert prioridades.filter(desde_proporcion=2).first().prioridad == 15
    assert prioridades.filter(desde_proporcion=2).first().categoria is None
    assert prioridades.filter(desde_proporcion=10).first().prioridad == 45
    assert prioridades.filter(desde_proporcion=10).first().hasta_proporcion == 100



def test_configuracion_seccion_set_hasta_cantidad_no_prioridad(db, settings):
    asignar_prioridades_standard(settings)
    seccion = SeccionFactory(cantidad_minima_prioridad_hasta_2=9)
    prioridades = PrioridadScheduling.objects.filter(seccion=seccion)
    assert prioridades.count() == 1
    assert prioridades.filter(desde_proporcion=0).first().prioridad == \
        settings.PRIORIDADES_STANDARD_SECCION[0]['prioridad']
    assert prioridades.filter(desde_proporcion=0).first().hasta_cantidad == 9


def test_cambio_prioridades_general(db, settings):
    """
    Se verifica el efecto de cambiar prioridades de una categoría o sección, en los orden_de_carga de las MesaCategoria.
    Se desarrolla una "historia" que combina identificaciones, cargas y cambios de prioridad.
    Se verifica que cada cambio de prioridades afecta exactamente a las MesaCategoria que corresponde.
    El autor pide disculpas por anticipado por la longitud de este test.
    """
    asignar_prioridades_standard(settings)
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    fiscal = nuevo_fiscal()

    seccion_1, circuito_1, lugar_votacion_1 = crear_seccion("Barrio maritimo")
    seccion_2, circuito_2, lugar_votacion_2 = crear_seccion("Bera centro")
    pv = CategoriaFactory(nombre="PV")
    gv = CategoriaFactory(nombre="GV")
    categorias = [pv, gv]

    mesas_seccion_1, mesas_seccion_2 = \
        crear_mesas([lugar_votacion_1, lugar_votacion_2], categorias, 20)

    # identifico las 10 primeras mesas de la sección 1
    for nro in range(10):
        identificar_mesa(mesas_seccion_1[nro], fiscal)

    # simulo carga total para las primeras 5 mesacat en orden de carga, 
    # van a ser, para la sección 1: mesa 0 - pv , mesa 0 - gv , mesa 1 - pv ,mesa 1 - gv , mesa 2 - pv
    verificar_siguiente_mesacat(mesas_seccion_1[0], pv)
    verificar_siguiente_mesacat(mesas_seccion_1[0], gv)
    verificar_siguiente_mesacat(mesas_seccion_1[1], pv)
    verificar_siguiente_mesacat(mesas_seccion_1[1], gv)
    verificar_siguiente_mesacat(mesas_seccion_1[2], pv)

    # ahora, identifico las 10 primeras mesas de la sección 2
    for nro in range(10):
        identificar_mesa(mesas_seccion_2[nro], fiscal)

    # verifico prioridades seteadas y no seteadas, hasta acá tienen el mismo orden de carga en ambas secciones
    # y en ambas categorías
    for mesas in [mesas_seccion_1, mesas_seccion_2]:
        verificar_valores_scheduling_mesacat(mesas[0], pv, 1, 1, 200)
        verificar_valores_scheduling_mesacat(mesas[0], gv, 1, 1, 200)
        verificar_valores_scheduling_mesacat(mesas[1], pv, 6, 2, 12000)
        verificar_valores_scheduling_mesacat(mesas[1], gv, 6, 2, 12000)
        verificar_valores_scheduling_mesacat(mesas[2], pv, 11, 3, 110000)
        verificar_valores_scheduling_mesacat(mesas[2], gv, 11, 3, 110000)
        verificar_valores_scheduling_mesacat(mesas[3], pv, 16, 4, 160000)
        verificar_valores_scheduling_mesacat(mesas[3], gv, 16, 4, 160000)
        verificar_valores_scheduling_mesacat(mesas[9], pv, 46, 10, 460000)
        verificar_valores_scheduling_mesacat(mesas[9], gv, 46, 10, 460000)
        verificar_valores_scheduling_mesacat(mesas[10], pv, None, None, None)
        verificar_valores_scheduling_mesacat(mesas[10], gv, None, None, None)

    # le cambio la prioridad a la categoría PV
    pv.prioridad = 15
    pv.save(update_fields=['prioridad'])

    # debería cambiar la prioridad para las mesacat que estén identificadas pero no tengan carga total
    verificar_valores_scheduling_mesacat(mesas_seccion_1[0], pv, 1, 1, 200)        # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[0], pv, 1, 1, 30)         # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_1[0], gv, 1, 1, 200)        # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[0], gv, 1, 1, 200)        # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_1[1], pv, 6, 2, 12000)      # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[1], pv, 6, 2, 1800)       # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_1[1], gv, 6, 2, 12000)      # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[1], gv, 6, 2, 12000)      # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_1[2], pv, 11, 3, 110000)    # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[2], pv, 11, 3, 16500)     # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_1[2], gv, 11, 3, 110000)    # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_2[2], gv, 11, 3, 110000)    # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_1[3], pv, 16, 4, 24000)     # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_2[3], pv, 16, 4, 24000)     # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_1[3], gv, 16, 4, 160000)    # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_2[3], gv, 16, 4, 160000)    # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_1[9], pv, 46, 10, 69000)    # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_2[9], pv, 46, 10, 69000)    # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_1[9], gv, 46, 10, 460000)   # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_2[9], gv, 46, 10, 460000)   # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_1[10], pv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[10], pv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_1[10], gv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[10], gv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_1[11], pv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[11], pv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_1[11], gv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[11], gv, None, None, None)          # no está identificada

    # identifico dos mesas más, una de cada sección. Me fijo que les asigne las prioridades adecuadas
    identificar_mesa(mesas_seccion_1[10], fiscal)
    identificar_mesa(mesas_seccion_2[10], fiscal)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[10], pv, 51, 11, 76500)
    verificar_valores_scheduling_mesacat(mesas_seccion_2[10], pv, 51, 11, 76500)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[10], gv, 51, 11, 510000)
    verificar_valores_scheduling_mesacat(mesas_seccion_2[10], gv, 51, 11, 510000)

    # cambio las prioridades de la sección 1
    seccion_1.prioridad_hasta_2 = 1
    seccion_1.prioridad_2_a_10 = 12
    seccion_1.prioridad_10_a_100 = 30
    seccion_1.save(update_fields=['prioridad_hasta_2', 'prioridad_2_a_10', 'prioridad_10_a_100'])

    # a ver ahora
    verificar_valores_scheduling_mesacat(mesas_seccion_1[0], pv, 1, 1, 200)        # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[0], pv, 1, 1, 30)         # no cambia la prioridad de esta sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[0], gv, 1, 1, 200)        # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[0], gv, 1, 1, 200)        # no cambia la prioridad de esta sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[1], pv, 6, 2, 12000)      # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[1], pv, 6, 2, 1800)       # no cambia la prioridad de esta sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[1], gv, 6, 2, 12000)      # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[1], gv, 6, 2, 12000)      # no cambia la prioridad de esta sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[2], pv, 11, 3, 110000)    # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[2], pv, 11, 3, 16500)     # no cambia la prioridad de esta sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[2], gv, 11, 3, 33000)     # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_2[2], gv, 11, 3, 110000)    # no cambia la prioridad de esta sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[3], pv, 16, 4, 7200)      # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_2[3], pv, 16, 4, 24000)     # no cambia la prioridad de esta sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[3], gv, 16, 4, 48000)     # no se cargó y está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[3], gv, 16, 4, 160000)    # no cambia la prioridad de esta sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[9], pv, 46, 10, 20700)    # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_2[9], pv, 46, 10, 69000)    # no cambia la prioridad de esta sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[9], gv, 46, 10, 138000)   # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_2[9], gv, 46, 10, 460000)   # no cambia la prioridad de esta sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[10], pv, 51, 11, 22950)   # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_2[10], pv, 51, 11, 76500)   # no cambia la prioridad de esta sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[10], gv, 51, 11, 153000)  # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_2[10], gv, 51, 11, 510000)  # no cambia la prioridad de esta sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[11], pv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[11], pv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_1[11], gv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[11], gv, None, None, None)          # no está identificada

    # simulo carga total para las siguientes 2 mesacat en orden de carga,
    # van a ser, para la sección 2: mesa 0 - pv , mesa 0 - gv
    verificar_siguiente_mesacat(mesas_seccion_2[0], pv)
    verificar_siguiente_mesacat(mesas_seccion_2[0], gv)

    # vuelvo la categoría PV a valores default
    pv.prioridad = None
    pv.save(update_fields=['prioridad'])

    # a ver cómo terminamos
    verificar_valores_scheduling_mesacat(mesas_seccion_1[0], pv, 1, 1, 200)        # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[0], pv, 1, 1, 30)         # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_1[0], gv, 1, 1, 200)        # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[0], gv, 1, 1, 200)        # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_1[1], pv, 6, 2, 12000)      # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[1], pv, 6, 2, 12000)      # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_1[1], gv, 6, 2, 12000)      # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[1], gv, 6, 2, 12000)      # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_1[2], pv, 11, 3, 110000)    # ya está cargada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[2], pv, 11, 3, 110000)    # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_1[2], gv, 11, 3, 33000)     # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_2[2], gv, 11, 3, 110000)    # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_1[3], pv, 16, 4, 48000)     # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_2[3], pv, 16, 4, 160000)    # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_1[3], gv, 16, 4, 48000)     # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_2[3], gv, 16, 4, 160000)    # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_1[9], pv, 46, 10, 138000)   # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_2[9], pv, 46, 10, 460000)   # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_1[9], gv, 46, 10, 138000)   # no cambia la prioridad de esta categoría 
    verificar_valores_scheduling_mesacat(mesas_seccion_2[9], gv, 46, 10, 460000)   # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_1[10], pv, 51, 11, 153000)  # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_2[10], pv, 51, 11, 510000)  # no se cargó y está identificada 
    verificar_valores_scheduling_mesacat(mesas_seccion_1[10], gv, 51, 11, 153000)  # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_2[10], gv, 51, 11, 510000)  # no cambia la prioridad de esta categoría
    verificar_valores_scheduling_mesacat(mesas_seccion_1[11], pv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[11], pv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_1[11], gv, None, None, None)          # no está identificada
    verificar_valores_scheduling_mesacat(mesas_seccion_2[11], gv, None, None, None)          # no está identificada


def test_cambio_prioridades_volver_parcialmente_a_default(db, settings):
    """
    Verifico que si para una sección, se vuelven algunos valores de prioridad al valor por defecto,
    entonces los orden_de_carga de las mesas se modifiquen de acuerdo a lo esperado.
    """
    asignar_prioridades_standard(settings)
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    fiscal = nuevo_fiscal()

    seccion_1, circuito_1, lugar_votacion_1 = crear_seccion("Barrio maritimo")
    pv = CategoriaFactory(nombre="PV")
    gv = CategoriaFactory(nombre="GV")
    categorias = [pv, gv]

    seccion_1.prioridad_hasta_2 = 1
    seccion_1.prioridad_2_a_10 = 12
    seccion_1.prioridad_10_a_100 = 30
    seccion_1.save(update_fields=['prioridad_hasta_2', 'prioridad_2_a_10', 'prioridad_10_a_100'])
    pv.prioridad = 35
    pv.save(update_fields=['prioridad'])

    [mesas_seccion_1] = crear_mesas([lugar_votacion_1], categorias, 100)
    # identifico todas las mesas
    for nro in range(100):
        identificar_mesa(mesas_seccion_1[nro], fiscal)

    # estado antes del cambio en las prioridades de la sección
    verificar_valores_scheduling_mesacat(mesas_seccion_1[0], pv, 1, 1, 35)        
    verificar_valores_scheduling_mesacat(mesas_seccion_1[0], gv, 1, 1, 100)        
    verificar_valores_scheduling_mesacat(mesas_seccion_1[1], pv, 2, 2, 70)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[1], gv, 2, 2, 200)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[2], pv, 3, 3, 1260)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[2], gv, 3, 3, 3600)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[9], pv, 10, 10, 4200)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[9], gv, 10, 10, 12000)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[10], pv, 11, 11, 11550)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[10], gv, 11, 11, 33000)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[40], pv, 41, 41, 43050)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[40], gv, 41, 41, 123000)
    
    # vuelvo al default el rango 2% - 10%
    seccion_1.prioridad_2_a_10 = None
    seccion_1.save(update_fields=['prioridad_2_a_10'])

    # a ver como quedaron
    verificar_valores_scheduling_mesacat(mesas_seccion_1[0], pv, 1, 1, 35)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[0], gv, 1, 1, 100)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[1], pv, 2, 2, 70)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[1], gv, 2, 2, 200)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[2], pv, 3, 3, 2100)        # está en el rango afectado por el cambio
    verificar_valores_scheduling_mesacat(mesas_seccion_1[2], gv, 3, 3, 6000)        # está en el rango afectado por el cambio
    verificar_valores_scheduling_mesacat(mesas_seccion_1[9], pv, 10, 10, 7000)      # está en el rango afectado por el cambio
    verificar_valores_scheduling_mesacat(mesas_seccion_1[9], gv, 10, 10, 20000)     # está en el rango afectado por el cambio
    verificar_valores_scheduling_mesacat(mesas_seccion_1[10], pv, 11, 11, 11550)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[10], gv, 11, 11, 33000)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[40], pv, 41, 41, 43050)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[40], gv, 41, 41, 123000)


def test_cambio_prioridades_asigno_cantidad_minima_mesas_maxima_prioridad(db, settings):
    """
    Verifico que si para una sección, se cambia únicamente la cantidad mínima de mesas 
    que deben considerarse para la máxima prioridad, 
    los orden_de_carga se actualizan en forma correcta
    """
    asignar_prioridades_standard(settings)
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 1
    fiscal = nuevo_fiscal()

    seccion_1, circuito_1, lugar_votacion_1 = crear_seccion("Barrio maritimo")
    pv = CategoriaFactory(nombre="PV")
    categorias = [pv]

    [mesas_seccion_1] = crear_mesas([lugar_votacion_1], categorias, 20)
    # identifico todas las mesas
    for nro in range(20):
        identificar_mesa(mesas_seccion_1[nro], fiscal)

    verificar_valores_scheduling_mesacat(mesas_seccion_1[0], pv, 1, 1, 200)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[1], pv, 6, 2, 12000)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[2], pv, 11, 3, 110000)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[6], pv, 31, 7, 310000)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[7], pv, 36, 8, 360000)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[8], pv, 41, 9, 410000)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[9], pv, 46, 10, 460000)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[18], pv, 91, 19, 910000)

    # asigno una cantidad mínima de mesas para la máxima prioridad
    seccion_1.cantidad_minima_prioridad_hasta_2 = 8
    seccion_1.save(update_fields=['cantidad_minima_prioridad_hasta_2'])

    verificar_valores_scheduling_mesacat(mesas_seccion_1[0], pv, 1, 1, 200)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[1], pv, 6, 2, 1200)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[2], pv, 11, 3, 2200)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[6], pv, 31, 7, 6200)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[7], pv, 36, 8, 7200)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[8], pv, 41, 9, 410000)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[9], pv, 46, 10, 460000)
    verificar_valores_scheduling_mesacat(mesas_seccion_1[18], pv, 91, 19, 910000)
