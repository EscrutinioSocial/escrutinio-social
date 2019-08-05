from elecciones.models import MesaCategoria
from adjuntos.consolidacion import consolidar_identificaciones

from elecciones.tests.factories import (
    MesaFactory, SeccionFactory, CircuitoFactory, LugarVotacionFactory,
    IdentificacionFactory, AttachmentFactory,
    UserFactory, FiscalFactory
)


def verificar_registro_prioridad(regi, desde_proporcion, hasta_proporcion, prioridad, hasta_cantidad=None):
    assert regi.desde_proporcion == desde_proporcion
    assert regi.hasta_proporcion == hasta_proporcion
    assert regi.prioridad == prioridad
    assert regi.hasta_cantidad == hasta_cantidad


def verificar_valores_scheduling_mesacat(mesa, cat, percentil, orden_de_llegada, orden_de_carga):
    mesacat = MesaCategoria.objects.filter(mesa=mesa, categoria=cat)[0]
    assert mesacat.percentil == percentil
    assert mesacat.orden_de_llegada == orden_de_llegada
    assert mesacat.orden_de_carga == orden_de_carga


def siguiente_mesa_a_cargar():
    mesacat = MesaCategoria.objects.siguiente()
    mesacat.status = MesaCategoria.STATUS.total_consolidada_dc
    mesacat.save(update_fields=['status'])
    return mesacat


def verificar_siguiente_mesacat(mesa, categoria, saltear=0):
    for ix in range(saltear+1):
        mesacat = siguiente_mesa_a_cargar()
    if not (mesacat.mesa == mesa and mesacat.categoria == categoria):
        print(f'verificación siguiente mesacat falla, la mesacat encontrada es:')
        print(f'mesa: {mesacat.mesa}  --  categoria: {mesacat.categoria}  --  orden de carga: {mesacat.orden_de_carga}')
    assert mesacat.mesa == mesa
    assert mesacat.categoria == categoria
    return mesacat


def asignar_prioridades_standard(settings):
    settings.PRIORIDADES_STANDARD_SECCION = [
        {'desde_proporcion': 0, 'hasta_proporcion': 2, 'prioridad': 2},
        {'desde_proporcion': 2, 'hasta_proporcion': 10, 'prioridad': 20},
        {'desde_proporcion': 10, 'hasta_proporcion': 100, 'prioridad': 100},
    ]
    settings.PRIORIDADES_STANDARD_CATEGORIA = [
        {'desde_proporcion': 0, 'hasta_proporcion': 100, 'prioridad': 100},
    ]


def nuevo_fiscal():
    usuario = UserFactory()
    fiscal = FiscalFactory(user=usuario)
    return fiscal


def crear_mesas(lugares_votacion, categorias, cantidad):
    mesas_creadas = []
    for lugar_votacion in lugares_votacion:
        mesas_creadas.append([])
    for nro in range(cantidad):
        indice_lugar_votacion = 0
        for lugar_votacion in lugares_votacion:
            numero_nueva_mesa = indice_lugar_votacion*1000+nro+1
            nueva_mesa = MesaFactory(
                lugar_votacion=lugar_votacion, numero=str(numero_nueva_mesa), categorias=categorias)
            mesas_creadas[indice_lugar_votacion].append(nueva_mesa)
            indice_lugar_votacion += 1
    return mesas_creadas


def crear_seccion(nombre):
    seccion = SeccionFactory(nombre="Barrio marítimo")
    circuito = CircuitoFactory(seccion=seccion)
    lugar_votacion = LugarVotacionFactory(circuito=circuito)
    return [seccion, circuito, lugar_votacion]


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
