import pytest
from django.core.management import call_command
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
from random import shuffle
from constance.test import override_config
from .factories import (
    VotoMesaReportadoFactory,
    CategoriaFactory,
    AttachmentFactory,
    MesaFactory,
    MesaCategoriaFactory,
    MesaCategoriaDefaultFactory,
    CargaFactory,
    IdentificacionFactory,
    CategoriaOpcionFactory,
    OpcionFactory,
    SeccionFactory,
    CircuitoFactory,
    DistritoFactory,
    FiscalFactory,
)
from elecciones.models import Mesa, MesaCategoria, Categoria, Carga, Opcion
from adjuntos.models import Identificacion
from adjuntos.consolidacion import consumir_novedades_carga, consumir_novedades_identificacion
from problemas.models import Problema, ReporteDeProblema


def consumir_novedades_y_actualizar_objetos(lista=None):
    consumir_novedades_carga()
    if not lista:
        return
    for item in lista:
        item.refresh_from_db()


def test_opciones_actuales(db):
    o2 = OpcionFactory()
    o3 = OpcionFactory()
    c = CategoriaFactory(opciones=[])
    co3 = CategoriaOpcionFactory(categoria=c, orden=2, opcion=o3)
    co2 = CategoriaOpcionFactory(categoria=c, orden=3, opcion=o2)
    o1 = CategoriaOpcionFactory(categoria=c, orden=1, prioritaria=True).opcion

    assert list(c.opciones_actuales()) == [
        o1, o3, o2,
        Opcion.blancos(), Opcion.total_votos(), Opcion.sobres(), Opcion.nulos(),
        Opcion.recurridos(), Opcion.id_impugnada(), Opcion.comando_electoral(),
    ]
    assert list(c.opciones_actuales(solo_prioritarias=True)) == [o1]
    assert list(c.opciones_actuales(excluir_optativas=True)) == [
        o1, o3, o2,
        Opcion.blancos(), Opcion.total_votos(), Opcion.nulos()
    ]


def test_categorias_para_mesa(db):
    e1, e2, e3 = CategoriaFactory.create_batch(3)
    e4 = CategoriaFactory(activa=False)
    m1 = MesaFactory(categorias=[e1, e2])
    m2 = MesaFactory(categorias=[e1, e2, e4])
    m3 = MesaFactory(categorias=[e1])
    m4 = MesaFactory(categorias=[e4])
    m5 = MesaFactory(categorias=[e1, e2])

    # no hay elecciones.comunes a todas las mesas
    assert not Categoria.para_mesas([m1, m2, m3, m4, m5]).exists()
    assert list(Categoria.para_mesas([m1, m2, m3, m5]).order_by('id')) == [e1]
    assert list(Categoria.para_mesas([m1, m2, m5]).order_by('id')) == [e1, e2]
    assert list(Categoria.para_mesas([m1, m3]).order_by('id')) == [e1]
    assert not Categoria.para_mesas([m2, m4]).exists()


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
    o1 = VotoMesaReportadoFactory(carga=c, votos=10).opcion
    o2 = VotoMesaReportadoFactory(carga=c, votos=8).opcion
    o3 = VotoMesaReportadoFactory(carga=c, votos=0).opcion
    # ignora otras
    VotoMesaReportadoFactory(votos=0)
    c.actualizar_firma()
    assert c.firma == f'{o1.id}-10|{o2.id}-8|{o3.id}-0'


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


def test_total_consolidada_multi_carga_con_minimo_1(db, settings):
    settings.MIN_COINCIDENCIAS_CARGAS = 1
    mc = MesaCategoriaFactory()
    assert mc.status == MesaCategoria.STATUS.sin_cargar
    c1 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-10')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mc.carga_testigo == c1


def test_consolidador_honra_timeout(db, settings):
    settings.MIN_COINCIDENCIAS_CARGAS = 1
    mc = MesaCategoriaFactory()
    assert mc.status == MesaCategoria.STATUS.sin_cargar
    c1 = CargaFactory(
        mesa_categoria=mc, tipo='total', firma='1-10',
        tomada_por_consolidador=timezone.now() - timedelta(minutes=settings.TIMEOUT_CONSOLIDACION - 1)
    )
    consumir_novedades_y_actualizar_objetos([mc, c1])
    # No la tomó aún.
    assert c1.procesada is False
    assert mc.status == MesaCategoria.STATUS.sin_cargar

    c1.tomada_por_consolidador = timezone.now() - timedelta(minutes=settings.TIMEOUT_CONSOLIDACION + 1)
    c1.save()

    # Ahora sí.
    consumir_novedades_y_actualizar_objetos([mc, c1])
    assert c1.procesada is True
    assert mc.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mc.carga_testigo == c1


def test_mc_status_carga_total_desde_mc_parcial(db):
    mc = MesaCategoriaFactory(
        status=MesaCategoria.STATUS.parcial_consolidada_dc,
    )
    c0 = CargaFactory(mesa_categoria=mc, tipo='parcial', firma='1-10')
    c1 = CargaFactory(mesa_categoria=mc, tipo='parcial', firma='1-10')
    mc.carga_testigo = c1
    mc.save()

    # Se asume que la carga total reusará los datos coincidentes de la carga parcial
    c2 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-10|2-20')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_sin_consolidar
    assert mc.carga_testigo == c2

    # Diverge
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

def test_carga_con_problemas(db):
    # Identifico una mesa.
    mesa = MesaFactory()
    a = AttachmentFactory()
    IdentificacionFactory(attachment=a, status='identificada', mesa=mesa)
    IdentificacionFactory(attachment=a, status='identificada', mesa=mesa)

    consumir_novedades_identificacion()
    mc = MesaCategoriaFactory(mesa=mesa, categoria=mesa.categorias.first())
    assert mc.status == MesaCategoria.STATUS.sin_cargar
    c1 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-10')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_sin_consolidar
    assert mc.carga_testigo == c1

    c2 = CargaFactory(mesa_categoria=mc, tipo='problema')
    Problema.reportar_problema(FiscalFactory(), 'reporte 1',
        ReporteDeProblema.TIPOS_DE_PROBLEMA.spam, carga=c2)
    consumir_novedades_y_actualizar_objetos([mc])

    # Sigue sin ser un problema.
    assert mc.status == MesaCategoria.STATUS.total_sin_consolidar
    assert mc.carga_testigo == c1
    assert c2.problemas.first().problema.estado == Problema.ESTADOS.potencial

    # Está entre las pendientes.
    assert mc in MesaCategoria.objects.con_carga_pendiente()

    c3 = CargaFactory(mesa_categoria=mc, tipo='problema')
    Problema.reportar_problema(FiscalFactory(), 'reporte 2',
        ReporteDeProblema.TIPOS_DE_PROBLEMA.ilegible, carga=c3)
    consumir_novedades_y_actualizar_objetos([mc])

    c2.refresh_from_db()
    c3.refresh_from_db()
    assert c2.invalidada == False
    assert c3.invalidada == False

    # Ahora sí hay un problema.
    assert mc.status == MesaCategoria.STATUS.con_problemas
    assert mc.carga_testigo is None
    problema = c2.problemas.first().problema
    assert problema.estado == Problema.ESTADOS.pendiente

    # No está entre las pendientes.
    assert mc not in MesaCategoria.objects.con_carga_pendiente()

    # Lo resolvemos.
    problema.resolver(FiscalFactory().user)

    assert problema.estado == Problema.ESTADOS.resuelto
    c1.refresh_from_db()
    c2.refresh_from_db()
    c3.refresh_from_db()
    assert c1.invalidada == False
    assert c2.invalidada == True
    assert c3.invalidada == True

    consumir_novedades_y_actualizar_objetos([mc])
    # El problema se solucionó también en la MesaCategoria.
    assert mc.status == MesaCategoria.STATUS.total_sin_consolidar
    assert mc.carga_testigo == c1

    # Está entre las pendientes.
    assert mc in MesaCategoria.objects.con_carga_pendiente()

    # Se mete otra carga y se consolida.
    c4 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-10')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_consolidada_dc
    assert mc.carga_testigo == c4 or mc.carga_testigo == c1

def test_problema_falta_foto(db):
    mc = MesaCategoriaFactory()
    assert mc.status == MesaCategoria.STATUS.sin_cargar
    c1 = CargaFactory(mesa_categoria=mc, tipo='total', firma='1-10')
    consumir_novedades_y_actualizar_objetos([mc])
    assert mc.status == MesaCategoria.STATUS.total_sin_consolidar
    assert mc.carga_testigo == c1

    c2 = CargaFactory(mesa_categoria=mc, tipo='problema')
    Problema.reportar_problema(FiscalFactory(), 'falta foto!',
        ReporteDeProblema.TIPOS_DE_PROBLEMA.falta_foto, carga=c2)
    c3 = CargaFactory(mesa_categoria=mc, tipo='problema')
    Problema.reportar_problema(FiscalFactory(), 'spam!',
        ReporteDeProblema.TIPOS_DE_PROBLEMA.spam, carga=c2)
    consumir_novedades_y_actualizar_objetos([mc])

    # Ahora sí hay un problema.
    assert mc.status == MesaCategoria.STATUS.con_problemas
    assert mc.carga_testigo is None
    problema = c2.problemas.first().problema
    assert problema.estado == Problema.ESTADOS.pendiente

    # Llega un nuevo attachment.
    a = AttachmentFactory()
    mesa = mc.mesa
    # Lo asocio a la misma mesa.
    IdentificacionFactory(attachment=a, status='identificada', mesa=mesa)
    IdentificacionFactory(attachment=a, status='identificada', mesa=mesa)

    consumir_novedades_identificacion()
    consumir_novedades_y_actualizar_objetos([mc])

    # El problema se solucionó.
    problema.refresh_from_db()
    assert problema.estado == Problema.ESTADOS.resuelto

    # La mesa está vigente de nuevo.
    assert mc.status == MesaCategoria.STATUS.total_sin_consolidar
    assert mc.carga_testigo == c1


def test_obtener_mesa_por_distrito_circuito_seccion_nro_no_encontrada(db):
    with pytest.raises(Mesa.DoesNotExist):
        Mesa.obtener_mesa_en_circuito_seccion_distrito(10, 10, 10, 10)


def test_obtener_mesa_por_distrito_circuito_seccion_nro_encontrada(db):
    d1 = DistritoFactory(numero='1')
    s1 = SeccionFactory(numero='50', distrito=d1)
    c1 = CircuitoFactory(numero=2, seccion=s1)
    MesaFactory(numero=4012, lugar_votacion__circuito=c1, electores=100, circuito=c1)
    mesa = Mesa.obtener_mesa_en_circuito_seccion_distrito(4012, 2, 50, 1)
    assert mesa.numero == '4012'
    assert mesa.circuito.numero == '2'
    assert mesa.circuito.seccion.numero == '50'
    assert mesa.circuito.seccion.distrito.numero == '1'


def test_metadata_de_mesa(db, settings):
    settings.MIN_COINCIDENCIAS_CARGAS = 1
    o1 = OpcionFactory(tipo=Opcion.TIPOS.metadata)
    o2 = OpcionFactory(tipo=Opcion.TIPOS.metadata)
    o3 = OpcionFactory()    # opcion comun
    # 2 categorias
    c1 = CategoriaFactory(opciones=[o1, o3])
    c2 = CategoriaFactory(opciones=[o1, o2, o3])

    # misma mesa
    mc1 = MesaCategoriaFactory(categoria=c1)
    mesa = mc1.mesa

    mc2 = MesaCategoriaFactory(categoria=c2, mesa=mesa)

    # carga categoria 1
    carga1 = CargaFactory(mesa_categoria=mc1, tipo='total')
    VotoMesaReportadoFactory(carga=carga1, opcion=o1, votos=10)
    VotoMesaReportadoFactory(carga=carga1, opcion=o3, votos=54)

    # como aun no hay cargas consolidadas, no hay metadata
    assert set(mesa.metadata()) == set()
    consumir_novedades_carga()

    # una vez consolidada, la mesa ya tiene metadatos accesibles
    mc1.refresh_from_db()
    assert mc1.status == MesaCategoria.STATUS.total_consolidada_dc
    assert set(mesa.metadata()) == {(o1.id, 10)}

    # carga 2 para otra categoria. tiene una metadata extra
    carga2 = CargaFactory(mesa_categoria=mc2, tipo='total')
    VotoMesaReportadoFactory(carga=carga2, opcion=o1, votos=10)
    VotoMesaReportadoFactory(carga=carga2, opcion=o2, votos=0)
    VotoMesaReportadoFactory(carga=carga2, opcion=o3, votos=54)

    consumir_novedades_carga()
    assert set(mesa.metadata()) == {(o1.id, 10), (o2.id, 0)}

    # reportes de metadata a otra mesa no afectan
    VotoMesaReportadoFactory(
        carga__mesa_categoria__status=MesaCategoria.STATUS.total_consolidada_dc,
        opcion=o1, votos=14
    )
    assert set(mesa.metadata()) == {(o1.id, 10), (o2.id, 0)}


def test_system_check_for_dev_data(db):
    call_command('loaddata', 'fixtures/dev_data.json')
    call_command('check', deploy=True)


def test_orden_por_prioridad_status(db):
    statuses = [s[0] for s in settings.MC_STATUS_CHOICE]

    # creo una mesa para cada status
    mcs = []
    for s in statuses:
        mcs.append(MesaCategoriaFactory(status=s).id)
    # el factory indirectamente crea otra mesa categoria para la default
    # las borro
    MesaCategoria.objects.exclude(id__in=mcs).delete()

    shuffle(statuses)
    with override_config(PRIORIDAD_STATUS='\n'.join(statuses)):
        mesas_result = MesaCategoria.objects.anotar_prioridad_status(
            ).order_by('prioridad_status')
    assert [m.status for m in mesas_result] == statuses


def test_normalizacion_numero(db):
    m = MesaFactory()

    # removemos ceros a la izquierda si es sólo números
    m.numero = "0001231"
    m.save()
    assert m.numero == "1231"

    # removemos espacios y ponemos en mayúsculas
    m.numero = "   as928"
    m.save()
    assert m.numero == "AS928"
    
    # si no son todos dígitos, no sacamos los ceros.
    s = SeccionFactory()
    s.numero = "00678vp"
    s.save()
    # ... pero si ponemos en mayúsculas
    assert s.numero == "00678VP"
