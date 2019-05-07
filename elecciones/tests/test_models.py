from datetime import timedelta
from .factories import (
    VotoMesaReportadoFactory,
    EleccionFactory,
    AttachmentFactory,
    MesaFactory,
    ProblemaFactory
)
from elecciones.models import Mesa
from django.utils import timezone


def test_mesa_siguiente_eleccion(db):
    e1, e2 = eleccion = EleccionFactory.create_batch(2)

    m1 = MesaFactory(eleccion=eleccion)
    assert m1.siguiente_eleccion_sin_carga() == e1
    VotoMesaReportadoFactory(mesa=m1, eleccion=e1, opcion=e1.opciones.first(), votos=10)
    assert m1.siguiente_eleccion_sin_carga() == e2
    VotoMesaReportadoFactory(mesa=m1, eleccion=e2, opcion=e2.opciones.first(), votos=10)
    assert m1.siguiente_eleccion_sin_carga() is None


def test_con_carga_pendiente_excluye_taken(db):
    m1 = AttachmentFactory().mesa
    m2 = AttachmentFactory().mesa
    assert set(Mesa.con_carga_pendiente()) == {m1, m2}
    m2.taken = timezone.now()
    m2.save()
    assert set(Mesa.con_carga_pendiente()) == {m1}


def test_con_carga_pendiente_incluye_taken_vencido(db):
    now = timezone.now()
    m1 = AttachmentFactory().mesa
    m2 = AttachmentFactory(mesa__taken=now - timedelta(minutes=3)).mesa
    assert set(Mesa.con_carga_pendiente()) == {m1, m2}


def test_con_carga_pendiente_excluye_si_tiene_problema_no_resuelto(db):
    m2 = AttachmentFactory().mesa
    m1 = AttachmentFactory().mesa
    ProblemaFactory(mesa=m1)
    assert set(Mesa.con_carga_pendiente()) == {m2}


def test_con_carga_pendiente_incluye_si_tiene_problema_resuelto(db):
    m2 = AttachmentFactory().mesa
    m1 = AttachmentFactory().mesa
    ProblemaFactory(mesa=m1, estado='resuelto')
    assert set(Mesa.con_carga_pendiente()) == {m1, m2}
    # nuevo problema
    ProblemaFactory(mesa=m1)
    assert set(Mesa.con_carga_pendiente()) == {m2}


def test_con_carga_pendiente_incluye_mesa_con_eleccion_sin_cargar(db):
    m1 = AttachmentFactory().mesa
    m2 = AttachmentFactory().mesa
    m3 = AttachmentFactory().mesa

    # mesa 2 ya se cargo, se excluirá
    eleccion = m2.eleccion.first()
    VotoMesaReportadoFactory(mesa=m2, eleccion=eleccion, opcion=eleccion.opciones.first(), votos=10)
    VotoMesaReportadoFactory(mesa=m2, eleccion=eleccion, opcion=eleccion.opciones.last(), votos=12)

    # para mesa 3 se cargó la primera eleccion, pero tiene mas elecciones pendientes
    m3.eleccion.add(EleccionFactory())
    m3.eleccion.add(EleccionFactory())
    eleccion = m3.eleccion.first()
    VotoMesaReportadoFactory(mesa=m3, eleccion=eleccion, opcion=eleccion.opciones.all()[0], votos=20)
    VotoMesaReportadoFactory(mesa=m3, eleccion=eleccion, opcion=eleccion.opciones.all()[1], votos=20)
    VotoMesaReportadoFactory(mesa=m3, eleccion=eleccion, opcion=eleccion.opciones.all()[2], votos=10)


    assert set(Mesa.con_carga_pendiente()) == {m1, m3}
