from .factories import (
    VotoMesaReportadoFactory,
    CategoriaFactory,
    AttachmentFactory,
    MesaFactory,
    MesaCategoriaFactory,
    CargaFactory,
    IdentificacionFactory,
    CategoriaOpcionFactory,
    OpcionFactory,
)
from elecciones.models import MesaCategoria, Categoria, Identificacion, Carga
from adjuntos.consolidacion import consumir_novedades_carga, consumir_novedades_identificacion


def consumir_novedades_y_actualizar_objetos(lista=None):
    consumir_novedades_carga()
    if not lista:
        return
    for item in lista:
        item.refresh_from_db()


def test_opciones_actuales(db):
    o2 = OpcionFactory(orden=3)
    o3 = OpcionFactory(orden=2)
    c = CategoriaFactory(opciones=[o2, o3])
    o1 = CategoriaOpcionFactory(categoria=c, opcion__orden=1, prioritaria=True).opcion
    assert list(c.opciones_actuales()) == [o1, o3, o2]
    assert list(c.opciones_actuales(solo_prioritarias=True)) == [o1]


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
        mesa_categoria=mc, tipo='parcial', firma='firma_1'
    )
    CargaFactory(
        mesa_categoria=mc, tipo='parcial', firma='firma_2')
    CargaFactory(mesa_categoria=mc, tipo='parcial', firma='firma_2')
    CargaFactory(mesa_categoria=mc, tipo='total', firma='firma_3')
    CargaFactory(mesa_categoria=mc, tipo='total', firma='firma_3')

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
    assert mc.status == MesaCategoria.STATUS.sin_cargar
    # se emula la firma de la carga
    c1 = CargaFactory(mesa_categoria=mc, tipo=Carga.TIPOS.parcial, firma='1-10')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.parcial_sin_consolidar
    assert mc.carga_testigo == c1

    # diverge
    c2 = CargaFactory(mesa_categoria=mc, tipo=Carga.TIPOS.parcial, firma='1-9')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.parcial_en_conflicto
    assert mc.carga_testigo is None

    # c2 coincide con c1
    c2 = CargaFactory(mesa_categoria=mc, tipo=Carga.TIPOS.parcial, firma='1-10')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.parcial_consolidada_dc
    assert mc.carga_testigo == c2 or mc.carga_testigo == c1


def test_mc_status_total_desde_mc_sin_carga(db):
    mc = MesaCategoriaFactory()
    assert mc.status == MesaCategoria.STATUS.sin_cargar
    c1 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-10')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_sin_consolidar
    assert mc.carga_testigo == c1

    # diverge
    c2 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-9')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_en_conflicto
    assert mc.carga_testigo is None

    # c2 coincide con c1
    c2 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-10')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mc.carga_testigo == c2 or mc.carga_testigo == c1


def test_mc_status_carga_total_desde_mc_parcial(db):
    mc = MesaCategoriaFactory(
        status=MesaCategoria.STATUS.parcial_consolidada_dc,
    )
    c1 = CargaFactory(mesa_categoria=mc, tipo='parcial', firma='1-10')
    mc.carga_testigo = c1
    mc.save()

    # se asume que la carga total reusará los datos coincidentes de la carga parcial
    c2 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-10|2-20')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_sin_consolidar
    assert mc.carga_testigo == c2

    # diverge
    c3 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-10|2-19')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_en_conflicto
    assert mc.carga_testigo is None

    # se asume que la carga total reusará los datos coincidentes de la carga parcial confirmada
    c4 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-10|2-20')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mc.carga_testigo == c4 or mc.carga_testigo == c2

def test_mc_status_carga_parcial_csv_desde_mc_sin_carga(db):
    mc = MesaCategoriaFactory()
    assert mc.status == MesaCategoria.STATUS.sin_cargar
    # se emula la firma de la carga
    c1 = CargaFactory(mesa_categoria=mc, tipo='parcial', origen=Carga.SOURCES.csv, firma='1-10')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.parcial_consolidada_csv
    assert mc.carga_testigo == c1

    # diverge pero prima csv
    c2 = CargaFactory(mesa_categoria=mc, tipo='parcial', firma='1-9')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.parcial_consolidada_csv
    assert mc.carga_testigo == c1

    # c2 coincide con c1
    c2 = CargaFactory(mesa_categoria=mc, tipo='parcial', firma='1-10')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.parcial_consolidada_dc
    assert mc.carga_testigo == c2 or mc.carga_testigo == c1


def test_mc_status_total_csv_desde_mc_sin_carga(db):
    mc = MesaCategoriaFactory()
    assert mc.status == MesaCategoria.STATUS.sin_cargar
    c1 = CargaFactory(mesa_categoria=mc, tipo='total', origen=Carga.SOURCES.csv, firma='1-10')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_consolidada_csv
    assert mc.carga_testigo == c1

    # diverge pero prima csv
    c2 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-9')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_consolidada_csv
    assert mc.carga_testigo == c1

    # c2 coincide con c1
    c2 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-10')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mc.carga_testigo == c2 or mc.carga_testigo == c1
