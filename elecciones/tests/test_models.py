from datetime import timedelta
from .factories import (
    VotoMesaReportadoFactory,
    CategoriaFactory,
    AttachmentFactory,
    MesaFactory,
    ProblemaFactory,
    IdentificacionFactory
)
from elecciones.models import Mesa, MesaCategoria, Categoria
from django.utils import timezone


def test_mesa_siguiente_categoria(db):
    e1, e2 = categoria = CategoriaFactory.create_batch(2)

    m1 = MesaFactory(categoria=categoria)
    assert m1.siguiente_categoria_sin_carga() == e1
    VotoMesaReportadoFactory(
        carga__mesa_categoria__mesa=m1,
        carga__mesa_categoria__categoria=e1,
        opcion=e1.opciones.first(),
        votos=10
    )
    assert m1.siguiente_categoria_sin_carga() == e2
    VotoMesaReportadoFactory(
        carga__mesa_categoria__mesa=m1,
        carga__mesa_categoria__categoria=e2,
        opcion=e2.opciones.first(),
        votos=10
    )
    assert m1.siguiente_categoria_sin_carga() is None


def test_mesa_siguiente_categoria_desactiva(db):
    e1, e2 = categorias = CategoriaFactory.create_batch(2)
    e2.activa = False
    e2.save()
    m1 = MesaFactory(categoria=categorias)
    assert m1.siguiente_categoria_sin_carga() == e1
    VotoMesaReportadoFactory(
        carga__mesa_categoria__mesa=m1,
        carga__mesa_categoria__categoria=e1,
        opcion=e1.opciones.first(), votos=10
    )
    assert m1.siguiente_categoria_sin_carga() is None


def test_con_carga_pendiente_excluye_sin_foto(db):
    m1 = MesaFactory()
    assert m1.attachments.count() == 0
    Mesa.con_carga_pendiente().count() == 0


def test_con_carga_pendiente_excluye_taken(db):
    m1 = IdentificacionFactory(status='identificada', consolidada=True).mesa
    m2 = IdentificacionFactory(status='identificada', consolidada=True).mesa
    assert set(Mesa.con_carga_pendiente()) == {m1, m2}
    m2.taken = timezone.now()
    m2.save()
    assert set(Mesa.con_carga_pendiente()) == {m1}


def test_con_carga_pendiente_incluye_taken_vencido(db):
    now = timezone.now()
    m1 = IdentificacionFactory(status='identificada', consolidada=True).mesa
    m2 = IdentificacionFactory(status='identificada', consolidada=True, mesa__taken=now - timedelta(minutes=3)).mesa
    assert set(Mesa.con_carga_pendiente()) == {m1, m2}


def test_con_carga_pendiente_excluye_si_tiene_problema_no_resuelto(db):
    m2 = IdentificacionFactory(status='identificada', consolidada=True).mesa
    m1 = IdentificacionFactory(status='identificada', consolidada=True).mesa
    ProblemaFactory(mesa=m1)
    assert set(Mesa.con_carga_pendiente()) == {m2}


def test_con_carga_pendiente_incluye_si_tiene_problema_resuelto(db):
    m2 = IdentificacionFactory(status='identificada', consolidada=True).mesa
    m1 = IdentificacionFactory(status='identificada', consolidada=True).mesa
    ProblemaFactory(mesa=m1, estado='resuelto')
    assert set(Mesa.con_carga_pendiente()) == {m1, m2}
    # nuevo problema
    ProblemaFactory(mesa=m1)
    assert set(Mesa.con_carga_pendiente()) == {m2}


def test_con_carga_pendiente_incluye_mesa_con_categoria_sin_cargar(db):
    m1 = IdentificacionFactory(status='identificada', consolidada=True).mesa
    m2 = IdentificacionFactory(status='identificada', consolidada=True).mesa
    m3 = IdentificacionFactory(status='identificada', consolidada=True).mesa

    # mesa 2 ya se cargo, se excluirá
    categoria = m2.categorias.first()
    VotoMesaReportadoFactory(carga__mesa_categoria__mesa=m2, carga__mesa_categoria__categoria=categoria, opcion=categoria.opciones.first(), votos=10)
    VotoMesaReportadoFactory(carga__mesa_categoria__mesa=m2, carga__mesa_categoria__categoria=categoria, opcion=categoria.opciones.last(), votos=12)

    # m3 tiene mas elecciones.pendientes
    e2 = CategoriaFactory(id=100)
    e3 = CategoriaFactory(id=101)
    e4 = CategoriaFactory(id=102)
    m3.categoria_add(e2)
    m3.categoria_add(e3)
    m3.categoria_add(e4)
    m3.categoria_add(CategoriaFactory(id=101))
    categoria = m3.categorias.first()
    # se cargo primera y segunda categoria para la mesa 3
    VotoMesaReportadoFactory(
        carga__mesa_categoria__mesa=m3,
        carga__mesa_categoria__categoria=categoria,
        opcion=categoria.opciones.first(),
        votos=20
    )
    VotoMesaReportadoFactory(
        carga__mesa_categoria__mesa=m3,
        carga__mesa_categoria__categoria=e2,
        opcion=e2.opciones.first(),
        votos=20
    )

    assert set(Mesa.con_carga_pendiente()) == {m1, m3}


# carga a confirmar

# def test_mesa_siguiente_categoria_a_confirmar(db):
#     e1, e2 = categoria = CategoriaFactory.create_batch(2)
#     m1 = MesaFactory(categoria=categoria)
#     VotoMesaReportadoFactory(
#         carga__mesa_categoria__mesa=m1,
#         carga__mesa_categoria__categoria=e1,
#         opcion=e1.opciones.first(),
#         votos=10
#     )
#     assert m1.siguiente_categoria_a_confirmar() == e1

#     # confirmo
#     me = MesaCategoria.objects.get(categoria=e1, mesa=m1)
#     me.confirmada = True
#     me.save()

#     assert m1.siguiente_categoria_a_confirmar() is None

#     # se cargó la otra categoria
#     VotoMesaReportadoFactory(
#         carga__mesa_categoria__mesa=m1,
#         carga__mesa_categoria__categoria=e2,
#         opcion=e2.opciones.first(),
#         votos=10
#     )
#     assert m1.siguiente_categoria_a_confirmar() == e2


# def test_mesa_siguiente_categoria_a_confirmar_categoria_desactivada(db):
#     e1 = CategoriaFactory(activa=False)
#     m1 = MesaFactory(categoria=[e1])
#     VotoMesaReportadoFactory(
#         carga__mesa_categoria__mesa=m1,
#         carga__mesa_categoria__categoria=e1,
#         opcion=e1.opciones.first(),
#         votos=10
#     )
#     # aunque haya datos cargados, la categoria desactivada la excluye de confirmacion
#     assert m1.siguiente_categoria_a_confirmar() is None


# def test_con_carga_a_confirmar(db):
#     e1, e2 = categoria = CategoriaFactory.create_batch(2)
#     m1 = MesaFactory(categoria=categoria)
#     m2 = MesaFactory(categoria=categoria)

#     VotoMesaReportadoFactory(carga__mesa_categoria__mesa=m1, carga__mesa_categoria__categoria=e1, opcion=e1.opciones.first(), votos=10)
#     assert set(Mesa.con_carga_a_confirmar()) == {m1}

#     VotoMesaReportadoFactory(carga__mesa_categoria__mesa=m2, carga__mesa_categoria__categoria=e1, opcion=e1.opciones.first(), votos=10)
#     assert set(Mesa.con_carga_a_confirmar()) == {m1, m2}

#     # confirmo la primer mesa.
#     # no hay mas elecciones.de m1 ya cargadas, por lo tanto no hay qué confirmar
#     me = MesaCategoria.objects.get(categoria=e1, mesa=m1)
#     me.confirmada = True
#     me.save()

#     assert set(Mesa.con_carga_a_confirmar()) == {m2}


# def test_con_carga_a_confirmar_categoria_desactivada(db):
#     e1 = CategoriaFactory(activa=False)
#     m1 = MesaFactory(categoria=[e1])
#     VotoMesaReportadoFactory(carga__mesa_categoria__mesa=m1, carga__mesa_categoria__categoria=e1, opcion=e1.opciones.first(), votos=10)
#     assert Mesa.con_carga_a_confirmar().count() == 0


def test_categorias_para_mesa(db):
    e1, e2, e3 = CategoriaFactory.create_batch(3)
    e4 = CategoriaFactory(activa=False)
    m1 = MesaFactory(categoria=[e1, e2])
    m2 = MesaFactory(categoria=[e1, e2, e4])
    m3 = MesaFactory(categoria=[e1])
    m4 = MesaFactory(categoria=[e4])
    m5 = MesaFactory(categoria=[e1, e2])

    # no hay elecciones.comunes a todas las mesas
    assert list(
        Categoria.para_mesas([m1, m2, m3, m4, m5]).order_by('id')
    ) == []

    # no hay elecciones.comunes a todas las mesas
    assert list(
        Categoria.para_mesas([m1, m2, m3, m5]).order_by('id')
    ) == [e1]

    assert list(
        Categoria.para_mesas([m1, m2, m5]).order_by('id')
    ) == [e1, e2]

    assert list(
        Categoria.para_mesas([m1, m3]).order_by('id')
    ) == [e1]

    assert list(
        Categoria.para_mesas([m2, m4]).order_by('id')
    ) == []


def test_fotos_de_mesa(db):
    m = MesaFactory()
    a1, a2, a3 = AttachmentFactory.create_batch(3)

    # a3 tiene una version editada.
    a3.foto_edited = a3.foto
    a3.save()

    IdentificacionFactory(
        status='identificada',
        consolidada=True,
        attachment=a1,
        mesa=m,
    )
    # a2 esta asociada a m pero se
    # ignorada porque no está consolidada
    IdentificacionFactory(
        status='identificada',
        consolidada=False,
        attachment=a2,
        mesa=m
    )
    IdentificacionFactory(
        status='identificada',
        consolidada=True,
        attachment=a3,
        mesa=m
    )
    assert m.fotos() == [
        ('Foto 1 (original)', a1.foto),
        ('Foto 2 (editada)', a3.foto_edited),
        ('Foto 2 (original)', a3.foto),
    ]