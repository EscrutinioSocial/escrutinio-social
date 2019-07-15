from datetime import timedelta
from .factories import (
    VotoMesaReportadoFactory,
    CategoriaFactory,
    AttachmentFactory,
    MesaFactory,
    MesaCategoriaFactory,
    ProblemaFactory,
    CargaFactory,
    IdentificacionFactory,
    CategoriaFactory,
    CategoriaOpcionFactory,
    OpcionFactory,
)
from elecciones.models import Mesa, MesaCategoria, Categoria
from django.utils import timezone
from adjuntos.consolidacion import *


def test_opciones_actuales(db):
    o2 = OpcionFactory(orden=3)
    o3 = OpcionFactory(orden=2)
    c = CategoriaFactory(opciones=[o2, o3])
    o1 = CategoriaOpcionFactory(categoria=c, opcion__orden=1, prioritaria=True).opcion
    assert list(c.opciones_actuales()) == [o1, o3, o2]
    assert list(c.opciones_actuales(solo_prioritarias=True)) == [o1]


def test_mesa_siguiente_categoria(db):
    e1, e2 = categorias = CategoriaFactory.create_batch(2)

    m1 = MesaFactory(categorias=categorias)
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
    m1 = MesaFactory(categorias=categorias)
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
    a1 = AttachmentFactory()
    m1 = IdentificacionFactory(status='identificada', attachment=a1).mesa
    IdentificacionFactory(status='identificada', attachment=a1, mesa=m1)
    a2 = AttachmentFactory()
    m2 = IdentificacionFactory(status='identificada', attachment=a2).mesa
    IdentificacionFactory(status='identificada', attachment=a2, mesa=m2)
    # Asocio el attach a la mesa.
    consumir_novedades_identificacion()
    assert set(Mesa.con_carga_pendiente()) == {m1, m2}
    m2.taken = timezone.now()
    m2.save()
    assert set(Mesa.con_carga_pendiente()) == {m1}


def test_con_carga_pendiente_incluye_taken_vencido(db):
    now = timezone.now()
    m1 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    m2 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv, mesa__taken=now - timedelta(minutes=3)).mesa
    consumir_novedades_identificacion()
    assert set(Mesa.con_carga_pendiente()) == {m1, m2}


def test_con_carga_pendiente_excluye_si_tiene_problema_no_resuelto(db):
    m2 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    m1 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    ProblemaFactory(mesa=m1)
    consumir_novedades_identificacion()
    assert set(Mesa.con_carga_pendiente()) == {m2}


def test_con_carga_pendiente_incluye_si_tiene_problema_resuelto(db):
    m2 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    m1 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    ProblemaFactory(mesa=m1, estado='resuelto')
    consumir_novedades_identificacion()
    assert set(Mesa.con_carga_pendiente()) == {m1, m2}
    # nuevo problema
    ProblemaFactory(mesa=m1)
    assert set(Mesa.con_carga_pendiente()) == {m2}


def test_con_carga_pendiente_incluye_mesa_con_categoria_sin_cargar(db):
    m1 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    m2 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa
    m3 = IdentificacionFactory(status='identificada', source=Identificacion.SOURCES.csv).mesa

    consumir_novedades_identificacion()

    # mesa 2 ya se cargó, se excluirá
    categoria = m2.categorias.first()
    VotoMesaReportadoFactory(carga__mesa_categoria__mesa=m2, carga__mesa_categoria__categoria=categoria, opcion=categoria.opciones.first(), votos=10)
    VotoMesaReportadoFactory(carga__mesa_categoria__mesa=m2, carga__mesa_categoria__categoria=categoria, opcion=categoria.opciones.last(), votos=12)

    # m3 tiene más elecciones.pendientes
    e2 = CategoriaFactory(id=100)
    e3 = CategoriaFactory(id=101)
    e4 = CategoriaFactory(id=102)
    m3.categoria_add(e2)
    m3.categoria_add(e3)
    m3.categoria_add(e4)
    m3.categoria_add(CategoriaFactory(id=101))
    categoria = m3.categorias.first()
    # Se cargó primera y segunda categoría para la mesa 3
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


def test_categorias_para_mesa(db):
    e1, e2, e3 = CategoriaFactory.create_batch(3)
    e4 = CategoriaFactory(activa=False)
    m1 = MesaFactory(categorias=[e1, e2])
    m2 = MesaFactory(categorias=[e1, e2, e4])
    m3 = MesaFactory(categorias=[e1])
    m4 = MesaFactory(categorias=[e4])
    m5 = MesaFactory(categorias=[e1, e2])

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
        source=Identificacion.SOURCES.csv,
        attachment=a1,
        mesa=m,
    )
    # a2 está asociada a m pero se
    # ignora porque no está consolidada.
    IdentificacionFactory(
        status='identificada',
        consolidada=False,
        attachment=a2,
        mesa=m
    )
    IdentificacionFactory(
        status='identificada',
        source=Identificacion.SOURCES.csv,
        attachment=a3,
        mesa=m
    )
    consumir_novedades_identificacion()
    assert m.fotos() == [
        ('Foto 1 (original)', a1.foto),
        ('Foto 2 (editada)', a3.foto_edited),
        ('Foto 2 (original)', a3.foto),
    ]


def test_carga_actualizar_firma(db):
    c = CargaFactory()
    o1 = VotoMesaReportadoFactory(carga=c, votos=10, opcion__orden=1).opcion
    o2 = VotoMesaReportadoFactory(carga=c, votos=8, opcion__orden=3).opcion
    o3 = VotoMesaReportadoFactory(carga=c, votos=None, opcion__orden=2).opcion
    # ignora otras
    VotoMesaReportadoFactory()
    c.actualizar_firma()
    assert c.firma == f'{o1.id}-10|{o3.id}-|{o2.id}-8'


def test_firma_count(db):
    mc = MesaCategoriaFactory()
    CargaFactory(
        mesa_categoria=mc, status='parcial', firma='firma_1'
    )
    CargaFactory(
        mesa_categoria=mc, status='parcial', firma='firma_2')
    CargaFactory(mesa_categoria=mc, status='parcial', firma='firma_2')
    CargaFactory(mesa_categoria=mc, status='total', firma='firma_3')
    CargaFactory(mesa_categoria=mc, status='total', firma='firma_3')

    assert mc.firma_count() == {
        'parcial': {
            'firma_1': 1,
            'firma_2': 2,
        },
        'total': {
            'firma_3': 2,
        }
    }


def test_mc_status_carga_parcial_desde_mc_sin_carga(db):
    mc = MesaCategoriaFactory()
    assert mc.status == 'sin_cargar'
    # se emula la firma de la carga
    c1 = CargaFactory(mesa_categoria=mc, status='parcial', firma='1-10')
    assert mc.status == 'parcial_sin_confirmar'
    assert mc.carga_testigo == c1

    # diverge
    c2 = CargaFactory(mesa_categoria=mc, status='parcial', firma='1-9')
    assert mc.status == 'parcial_en_conflicto'
    assert mc.carga_testigo is None

    # c2 coincide con c1
    c2 = CargaFactory(mesa_categoria=mc, status='parcial', firma='1-10')
    assert mc.status == 'parcial_confirmada'
    assert mc.carga_testigo == c2


def test_mc_status_total_desde_mc_sin_carga(db):
    mc = MesaCategoriaFactory()
    assert mc.status == 'sin_cargar'
    c1 = CargaFactory(mesa_categoria=mc, status='total', firma='1-10')
    assert mc.status == 'total_sin_confirmar'
    assert mc.carga_testigo == c1

    # diverge
    c2 = CargaFactory(mesa_categoria=mc, status='total', firma='1-9')
    assert mc.status == 'total_en_conflicto'
    assert mc.carga_testigo is None

    # c2 coincide con c1
    c2 = CargaFactory(mesa_categoria=mc, status='total', firma='1-10')
    assert mc.status == 'total_confirmada'
    assert mc.carga_testigo == c2


def test_mc_status_carga_total_desde_mc_parcial(db):
    mc = MesaCategoriaFactory(
        status='parcial_confirmada',
    )
    c1 = CargaFactory(mesa_categoria=mc, status='parcial', firma='1-10')
    mc.carga_testigo = c1
    mc.save()

    # se asume que la carga total reusará los datos coincidentes de la carga parcial
    c2 = CargaFactory(mesa_categoria=mc, status='total', firma='1-10|2-20')
    assert mc.status == 'total_sin_confirmar'
    assert mc.carga_testigo == c2

    # diverge
    c3 = CargaFactory(mesa_categoria=mc, status='total', firma='1-10|2-19')
    assert mc.status == 'total_en_conflicto'
    assert mc.carga_testigo is None

    # se asume que la carga total reusará los datos coincidentes de la carga parcial confirmada
    c4 = CargaFactory(mesa_categoria=mc, status='total', firma='1-10|2-20')
    assert mc.status == 'total_confirmada'
    assert mc.carga_testigo == c4
