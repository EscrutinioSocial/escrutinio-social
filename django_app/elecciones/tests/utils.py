from elecciones.models import Distrito, Seccion
from .factories import (
    DistritoFactory,
    SeccionFactory,
    CircuitoFactory,
    MesaFactory,
    VotoMesaReportadoFactory,
    TecnicaProyeccionFactory,
    AgrupacionCircuitosFactory,
)


def create_carta_marina(create_distritos=1):
    """
    1 distrito, 2 secciones con 2 circuitos y 2 mesas por circuito
    """
    distritos = DistritoFactory.create_batch(create_distritos
                                             ) if create_distritos > 0 else Distrito.objects.filter(numero=1)

    mesas = []
    for d in distritos:
        s1, s2 = SeccionFactory.create_batch(2, distrito=d)
        c1, c2 = CircuitoFactory.create_batch(2, seccion=s1)
        c3, c4 = CircuitoFactory.create_batch(2, seccion=s2)
        mesas.extend([
            MesaFactory(numero=1, lugar_votacion__circuito=c1, electores=100),
            MesaFactory(numero=2, lugar_votacion__circuito=c1, electores=100),
            MesaFactory(numero=3, lugar_votacion__circuito=c2, electores=120),
            MesaFactory(numero=4, lugar_votacion__circuito=c2, electores=120),
            MesaFactory(numero=5, lugar_votacion__circuito=c3, electores=90),
            MesaFactory(numero=6, lugar_votacion__circuito=c3, electores=90),
            MesaFactory(numero=7, lugar_votacion__circuito=c4, electores=90),
            MesaFactory(numero=8, lugar_votacion__circuito=c4, electores=90),
        ])

    return mesas


def tecnica_proyeccion(minimo_mesas=1):
    """
    Crea una técnica de proyección para las mesas existentes, agrupadas por sección.
    """
    proyeccion = TecnicaProyeccionFactory()
    for seccion in Seccion.objects.all():
        AgrupacionCircuitosFactory(
            nombre=seccion.nombre,
            proyeccion=proyeccion,
            minimo_mesas=minimo_mesas
        ).circuitos.set(seccion.circuitos.all())

    return proyeccion


def cargar_votos(carga, votos):
    for opcion, cant_votos in votos.items():
        VotoMesaReportadoFactory(opcion=opcion, carga=carga, votos=cant_votos)
    carga.actualizar_firma()
