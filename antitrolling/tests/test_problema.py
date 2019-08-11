from elecciones.tests.factories import (
    CargaFactory,
    CategoriaFactory,
    CategoriaOpcionFactory,
    FiscalFactory,
    AttachmentFactory,
    IdentificacionFactory,
    UserFactory,
    VotoMesaReportadoFactory,
    CircuitoFactory, SeccionFactory, LugarVotacionFactory, MesaFactory,
)
from adjuntos.models import Identificacion
from elecciones.models import MesaCategoria
from problemas.models import Problema, ReporteDeProblema
from adjuntos.consolidacion import (
    consumir_novedades_carga, consumir_novedades_identificacion
)
from .utils_para_test import (nuevo_fiscal, reportar_problema_attachment, reportar_problema_mesa_categoria, nueva_categoria)


def test_identificacion_problema_troll(db):
    fiscal_troll = nuevo_fiscal()
    fiscal_troll.troll = True
    fiscal_troll.save(update_fields=['troll'])
    fiscal_ok = nuevo_fiscal()

    attach = AttachmentFactory()
    ident_troll = reportar_problema_attachment(attach, fiscal_troll)
    Problema.reportar_problema(fiscal_troll, "foto fea", ReporteDeProblema.TIPOS_DE_PROBLEMA.ilegible, identificacion=ident_troll)
    ident_ok = reportar_problema_attachment(attach, fiscal_ok)
    Problema.reportar_problema(fiscal_ok, "no me gusta",
                               ReporteDeProblema.TIPOS_DE_PROBLEMA.falta_lista, identificacion=ident_ok)

    assert 2 == Problema.objects.count()
    assert 1 == ReporteDeProblema.objects.filter(reportado_por=fiscal_troll).count()
    assert 1 == ReporteDeProblema.objects.filter(reportado_por=fiscal_ok).count()

    problema_troll = ReporteDeProblema.objects.filter(reportado_por=fiscal_troll).first().problema
    assert Problema.ESTADOS.descartado == problema_troll.estado
    problema_ok = ReporteDeProblema.objects.filter(reportado_por=fiscal_ok).first().problema
    assert Problema.ESTADOS.potencial == problema_ok.estado


def test_carga_problema_troll(db):
    fiscal_troll = nuevo_fiscal()
    fiscal_troll.troll = True
    fiscal_troll.save(update_fields=['troll'])
    fiscal_ok = nuevo_fiscal()

    categ = nueva_categoria(["a", "b"])
    mesa = MesaFactory(categorias=[categ])
    mesa_categoria = MesaCategoria.objects.filter(mesa=mesa).first()

    carga_troll = reportar_problema_mesa_categoria(mesa_categoria, fiscal_troll)
    Problema.reportar_problema(fiscal_troll, "foto fea",
                               ReporteDeProblema.TIPOS_DE_PROBLEMA.ilegible, carga=carga_troll)
    carga_ok = reportar_problema_mesa_categoria(mesa_categoria, fiscal_ok)
    Problema.reportar_problema(fiscal_ok, "no me gusta",
                               ReporteDeProblema.TIPOS_DE_PROBLEMA.falta_lista, carga=carga_ok)

    assert 2 == Problema.objects.count()
    assert 1 == ReporteDeProblema.objects.filter(reportado_por=fiscal_troll).count()
    assert 1 == ReporteDeProblema.objects.filter(reportado_por=fiscal_ok).count()

    problema_troll = ReporteDeProblema.objects.filter(reportado_por=fiscal_troll).first().problema
    assert Problema.ESTADOS.descartado == problema_troll.estado
    problema_ok = ReporteDeProblema.objects.filter(reportado_por=fiscal_ok).first().problema
    assert Problema.ESTADOS.potencial == problema_ok.estado
