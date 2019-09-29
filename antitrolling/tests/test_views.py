import pytest
from constance.test import override_config

from antitrolling.models import (
    EventoScoringTroll, CambioEstadoTroll,
    aplicar_marca_troll,
    aumentar_scoring_troll_identificacion, aumentar_scoring_troll_carga,
    disminuir_scoring_troll_identificacion, disminuir_scoring_troll_carga
)
from elecciones.models import MesaCategoria, Carga
from fiscales.models import Fiscal

from elecciones.tests.factories import (
    MesaFactory, AttachmentFactory, CategoriaFactory
)

from .utils_para_test import (
    nuevo_fiscal, identificar, reportar_problema_attachment,
    nueva_categoria, nueva_carga
)

from antitrolling.views import (
    FiscalesEnRangoScoringTroll, ParametrosAntitrolling, IndicadorDePeligro,
    FiscalesTroll, FiscalesNoTroll, GeneradorInfoAcciones
)

def test_data_fiscales_para_monitoreo_antitrolling(db):
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()
    fiscal_3 = nuevo_fiscal()
    fiscal_4 = nuevo_fiscal()
    fiscal_5 = nuevo_fiscal()
    fiscal_6 = nuevo_fiscal()
    fiscal_7 = nuevo_fiscal()
    fiscal_8 = nuevo_fiscal()

    attach = AttachmentFactory()
    mesa_1 = MesaFactory()
    mesa_2 = MesaFactory()
    mesa_3 = MesaFactory()
    mesa_4 = MesaFactory()
    mesa_5 = MesaFactory()


    with override_config(SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL=500):        
        identi_1 = reportar_problema_attachment(attach, fiscal_1)
        identi_2 = identificar(attach, mesa_1, fiscal_2)
        identi_3 = identificar(attach, mesa_2, fiscal_3)
        identi_4 = identificar(attach, mesa_3, fiscal_4)
        identi_5 = identificar(attach, mesa_4, fiscal_5)
        identi_6 = identificar(attach, mesa_5, fiscal_6)

        aumentar_scoring_troll_identificacion(300, identi_1)
        aumentar_scoring_troll_identificacion(450, identi_2)
        aumentar_scoring_troll_identificacion(520, identi_3)
        aumentar_scoring_troll_identificacion(100, identi_4)
        aumentar_scoring_troll_identificacion(51, identi_5)
        aumentar_scoring_troll_identificacion(30, identi_6)

        # sólo toma en cuenta los fiscales que ingresaron alguna vez
        for fiscal in [fiscal_1, fiscal_2, fiscal_3, fiscal_4, fiscal_5, fiscal_6, fiscal_7, fiscal_8]:
            fiscal.marcar_ingreso_alguna_vez()
            fiscal.refresh_from_db()

        ParametrosAntitrolling.reset()

        rango_80 = FiscalesEnRangoScoringTroll().setRangoPorcentajes(80, None).set_umbrales_de_peligro(5, 7, 10)
        assert rango_80.cantidad_fiscales() == 1
        assert rango_80.porcentaje_fiscales() == 12.5
        assert rango_80.desde_scoring == 401
        assert rango_80.hasta_scoring == None
        assert rango_80.indicador_peligro() == IndicadorDePeligro.indicador_rojo

        rango_intermedio = FiscalesEnRangoScoringTroll().setRangoPorcentajes(30, 60).set_umbrales_de_peligro(30, 40, 50)
        assert rango_intermedio.cantidad_fiscales() == 1
        assert rango_intermedio.porcentaje_fiscales() == 12.5
        assert rango_intermedio.desde_scoring == 151
        assert rango_intermedio.hasta_scoring == 300
        assert rango_intermedio.indicador_peligro() == IndicadorDePeligro.indicador_verde

        rango_amplio = FiscalesEnRangoScoringTroll().setRangoPorcentajes(10, 60).set_umbrales_de_peligro(30, 40, 50)
        assert rango_amplio.cantidad_fiscales() == 3
        assert rango_amplio.porcentaje_fiscales() == 37.5
        assert rango_amplio.desde_scoring == 51
        assert rango_amplio.hasta_scoring == 300
        assert rango_amplio.indicador_peligro() == IndicadorDePeligro.indicador_amarillo

        data_troll = FiscalesTroll().set_umbrales_de_peligro(5, 10, 15)
        assert data_troll.cantidad_fiscales() == 1
        assert data_troll.porcentaje_fiscales() == 12.5
        assert data_troll.indicador_peligro() == IndicadorDePeligro.indicador_naranja

        attach_2 = AttachmentFactory()
        identi_2_2 = identificar(attach, mesa_1, fiscal_2)
        aumentar_scoring_troll_identificacion(120, identi_2_2)
        data_troll = FiscalesTroll().set_umbrales_de_peligro(5, 10, 15)
        assert data_troll.cantidad_fiscales() == 2
        assert data_troll.porcentaje_fiscales() == 25
        assert data_troll.indicador_peligro() == IndicadorDePeligro.indicador_rojo
        data_no_troll = FiscalesNoTroll(data_troll)
        assert data_no_troll.cantidad_fiscales() == 6
        assert data_no_troll.porcentaje_fiscales() == 75


def test_data_acciones_para_monitoreo_antitrolling(db):
    # 40 mesas con su mesacat
    # 30 cargas, 22 procesadas, de esas 1 inválidas
    # de las 8 no procesadas, 2 inválidas

    presi = CategoriaFactory()
    fiscal = nuevo_fiscal()
    for ix in range(40):
        nueva_mesa = MesaFactory(categorias=[presi])
        mesacat = MesaCategoria.objects.filter(mesa=nueva_mesa, categoria=presi).first()
        if (ix < 30):
            carga = nueva_carga(mesacat, fiscal, [20,15], Carga.TIPOS.parcial)
            if (ix < 1):
                carga.invalidada = True
                carga.procesada = True
            elif (ix < 22):
                carga.invalidada = False
                carga.procesada = True
            elif (ix < 24):
                carga.invalidada = True
                carga.procesada = False
            else:
                carga.invalidada = False
                carga.procesada = False
            carga.save(update_fields=['invalidada', 'procesada'])

    ParametrosAntitrolling.reset()
    rangos = GeneradorInfoAcciones(Carga.objects).rangos()
    rango_total = next(rango for rango in rangos if rango.texto == 'Total')
    assert rango_total.cantidad == 30
    assert rango_total.porcentaje == 100
    rango_validas = next(rango for rango in rangos if rango.texto == 'Válidas procesadas')
    assert rango_validas.cantidad == 21
    assert rango_validas.porcentaje == 70
    rango_pendientes = next(rango for rango in rangos if rango.texto == 'Pendientes de proceso')
    assert rango_pendientes.cantidad == 6
    assert rango_pendientes.porcentaje == 20
    rango_invalidas = next(rango for rango in rangos if rango.texto == 'Invalidadas')
    assert rango_invalidas.cantidad == 3
    assert rango_invalidas.porcentaje == 10
    assert rango_invalidas.indicador_peligro == IndicadorDePeligro.indicador_rojo

    # con otros valores de peligro, corresponde otro indicador para el mismo porcentaje
    rango_invalidas.set_umbrales_de_peligro(8, 15, 30)
    assert rango_invalidas.cantidad == 3
    assert rango_invalidas.porcentaje == 10
    assert rango_invalidas.indicador_peligro == IndicadorDePeligro.indicador_amarillo
    rango_invalidas.set_umbrales_de_peligro(28, 35, 50)
    assert rango_invalidas.cantidad == 3
    assert rango_invalidas.porcentaje == 10
    assert rango_invalidas.indicador_peligro == IndicadorDePeligro.indicador_verde
    




