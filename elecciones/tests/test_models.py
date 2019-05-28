from datetime import timedelta
from .factories import (
    VotoMesaReportadoFactory,
    EleccionFactory,
    AttachmentFactory,
    MesaFactory,
    ProblemaFactory
)
from elecciones.models import Mesa, MesaEleccion, Eleccion
from django.utils import timezone


def test_mesa_siguiente_eleccion(db):
    e1, e2 = eleccion = EleccionFactory.create_batch(2)

    m1 = MesaFactory(eleccion=eleccion)
    assert m1.siguiente_eleccion_sin_carga() == e1
    VotoMesaReportadoFactory(mesa=m1, eleccion=e1, opcion=e1.opciones.first(), votos=10)
    assert m1.siguiente_eleccion_sin_carga() == e2
    VotoMesaReportadoFactory(mesa=m1, eleccion=e2, opcion=e2.opciones.first(), votos=10)
    assert m1.siguiente_eleccion_sin_carga() is None


def test_mesa_siguiente_eleccion_desactiva(db):
    e1, e2 = elecciones = EleccionFactory.create_batch(2)
    e2.activa = False
    e2.save()
    m1 = MesaFactory(eleccion=elecciones)
    assert m1.siguiente_eleccion_sin_carga() == e1
    VotoMesaReportadoFactory(mesa=m1, eleccion=e1, opcion=e1.opciones.first(), votos=10)
    assert m1.siguiente_eleccion_sin_carga() is None


def test_con_carga_pendiente_excluye_sin_foto(db):
    m1 = MesaFactory()
    assert m1.attachments.count() == 0
    Mesa.con_carga_pendiente().count() == 0


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

    # m3 tiene mas elecciones pendientes
    e2 = EleccionFactory(id=100)
    e3 = EleccionFactory(id=101)
    e4 = EleccionFactory(id=102)
    m3.eleccion_add(e2)
    m3.eleccion_add(e3)
    m3.eleccion_add(e4)
    m3.eleccion_add(EleccionFactory(id=101))
    eleccion = m3.eleccion.first()
    # se cargo primera y segunda eleccion para la mesa 3
    VotoMesaReportadoFactory(mesa=m3, eleccion=eleccion, opcion=eleccion.opciones.first(), votos=20)
    VotoMesaReportadoFactory(mesa=m3, eleccion=e2, opcion=e2.opciones.first(), votos=20)

    assert set(Mesa.con_carga_pendiente()) == {m1, m3}


# carga a confirmar

def test_mesa_siguiente_eleccion_a_confirmar(db):
    e1, e2 = eleccion = EleccionFactory.create_batch(2)
    m1 = MesaFactory(eleccion=eleccion)
    VotoMesaReportadoFactory(mesa=m1, eleccion=e1, opcion=e1.opciones.first(), votos=10)

    assert m1.siguiente_eleccion_a_confirmar() == e1

    # confirmo
    me = MesaEleccion.objects.get(eleccion=e1, mesa=m1)
    me.confirmada = True
    me.save()

    assert m1.siguiente_eleccion_a_confirmar() is None

    # se cargó la otra eleccion
    VotoMesaReportadoFactory(mesa=m1, eleccion=e2, opcion=e2.opciones.first(), votos=10)
    assert m1.siguiente_eleccion_a_confirmar() == e2


def test_mesa_siguiente_eleccion_a_confirmar_eleccion_desactivada(db):
    e1 = EleccionFactory(activa=False)
    m1 = MesaFactory(eleccion=[e1])
    VotoMesaReportadoFactory(mesa=m1, eleccion=e1, opcion=e1.opciones.first(), votos=10)
    # aunque haya datos cargados, la eleccion desactivada la excluye de confirmacion
    assert m1.siguiente_eleccion_a_confirmar() is None


def test_con_carga_a_confirmar(db):
    e1, e2 = eleccion = EleccionFactory.create_batch(2)
    m1 = MesaFactory(eleccion=eleccion)
    m2 = MesaFactory(eleccion=eleccion)

    VotoMesaReportadoFactory(mesa=m1, eleccion=e1, opcion=e1.opciones.first(), votos=10)
    assert set(Mesa.con_carga_a_confirmar()) == {m1}

    VotoMesaReportadoFactory(mesa=m2, eleccion=e1, opcion=e1.opciones.first(), votos=10)
    assert set(Mesa.con_carga_a_confirmar()) == {m1, m2}

    # confirmo la primer mesa.
    # no hay mas elecciones de m1 ya cargadas, por lo tanto no hay qué confirmar
    me = MesaEleccion.objects.get(eleccion=e1, mesa=m1)
    me.confirmada = True
    me.save()

    assert set(Mesa.con_carga_a_confirmar()) == {m2}


def test_con_carga_a_confirmar_eleccion_desactivada(db):
    e1 = EleccionFactory(activa=False)
    m1 = MesaFactory(eleccion=[e1])
    VotoMesaReportadoFactory(mesa=m1, eleccion=e1, opcion=e1.opciones.first(), votos=10)
    assert Mesa.con_carga_a_confirmar().count() == 0


def test_elecciones_para_mesa(db):
    e1, e2, e3 = EleccionFactory.create_batch(3)
    e4 = EleccionFactory(activa=False)
    m1 = MesaFactory(eleccion=[e1, e2])
    m2 = MesaFactory(eleccion=[e1, e2, e4])
    m3 = MesaFactory(eleccion=[e1])
    m4 = MesaFactory(eleccion=[e4])
    m5 = MesaFactory(eleccion=[e1, e2])

    # no hay elecciones comunes a todas las mesas
    assert list(
        Eleccion.para_mesas([m1, m2, m3, m4, m5]).order_by('id')
    ) == []

    # no hay elecciones comunes a todas las mesas
    assert list(
        Eleccion.para_mesas([m1, m2, m3, m5]).order_by('id')
    ) == [e1]

    assert list(
        Eleccion.para_mesas([m1, m2, m5]).order_by('id')
    ) == [e1, e2]

    assert list(
        Eleccion.para_mesas([m1, m3]).order_by('id')
    ) == [e1]

    assert list(
        Eleccion.para_mesas([m2, m4]).order_by('id')
    ) == []
