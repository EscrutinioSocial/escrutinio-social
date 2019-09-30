import pytest

from elecciones.tests.factories import (
    MesaFactory, AttachmentFactory, PreidentificacionFactory,
    DistritoFactory, SeccionFactory, CircuitoFactory, LugarVotacionFactory
)
from elecciones.tests.utils_para_test import (
    nuevo_fiscal, identificar, reportar_problema_attachment
)
from adjuntos.consolidacion import consumir_novedades
from elecciones.models import Mesa
from adjuntos.models import Attachment, PreIdentificacion
from elecciones.resultados_resumen import (
    GeneradorDatosFotosNacional, GeneradorDatosFotosDistrital, GeneradorDatosPreidentificaciones
)


class DataTresDistritos():
    def __init__(self):
        self.distrito_caba = DistritoFactory(numero='1')
        self.seccion_caba = SeccionFactory(distrito=self.distrito_caba)
        self.circuito_caba = CircuitoFactory(seccion=self.seccion_caba)
        self.lugar_votacion_caba = LugarVotacionFactory(circuito=self.circuito_caba)
        self.distrito_pba = DistritoFactory(numero='2')
        self.seccion_pba = SeccionFactory(distrito=self.distrito_pba)
        self.circuito_pba = CircuitoFactory(seccion=self.seccion_pba)
        self.lugar_votacion_pba = LugarVotacionFactory(circuito=self.circuito_pba)
        self.distrito_cat = DistritoFactory(numero='3')
        self.seccion_cat = SeccionFactory(distrito=self.distrito_cat)
        self.circuito_cat = CircuitoFactory(seccion=self.seccion_cat)
        self.lugar_votacion_cat = LugarVotacionFactory(circuito=self.circuito_cat)
        self.fiscales = [nuevo_fiscal() for ix in range(10)]
        self.mesas_caba = [MesaFactory(lugar_votacion=self.lugar_votacion_caba, circuito=self.circuito_caba)
                    for ix in range(15)]
        self.mesas_cat = [MesaFactory(lugar_votacion=self.lugar_votacion_cat, 
                                      circuito=self.circuito_cat) for ix in range(15)]
        self.mesas_pba = [MesaFactory(lugar_votacion=self.lugar_votacion_pba,
                                      circuito=self.circuito_pba) for ix in range(20)]


def test_datos_fotos_nacional(db, settings):
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2

    fiscales = [nuevo_fiscal() for ix in range(10)]
    mesas = [MesaFactory() for ix in range(30)]

    # 25 fotos:
    # - 9 identificadas
    # - 1 con problemas
    # - 8 en proceso de identificación
    # - 7 sin acciones
    for ix in range(25):
        foto = AttachmentFactory()
        if (ix < 9):
            identificar(foto, mesas[ix], fiscales[0])
            identificar(foto, mesas[ix], fiscales[1])
        elif (ix < 10):
            reportar_problema_attachment(foto, fiscales[2])
            reportar_problema_attachment(foto, fiscales[3])
        elif (ix < 18):
            identificar(foto, mesas[ix], fiscales[4])

    consumir_novedades()
    generador = GeneradorDatosFotosNacional()
    generador.calcular()

    assert generador.cantidad_mesas == 30
    assert generador.mesas_con_foto_identificada == 9
    assert generador.fotos_con_problema_confirmado == 1
    assert generador.fotos_en_proceso == 8
    assert generador.fotos_sin_acciones == 7
    assert generador.mesas_sin_foto == 5


def test_datos_fotos_distrital(db, settings):
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2
    settings.DISTRITO_PBA = '2'

    # 50 mesas: 20 pba, 15 caba, 15 catamarca
    data = DataTresDistritos()

    # 40 fotos:
    # - 14 / 5 / 2 identificadas a mesas pba / caba / catamarca
    # - 3 con problemas
    # - 6 en proceso de identificación
    # - 10 sin acciones
    for ix in range(40):
        foto = AttachmentFactory()
        if (ix < 14):
            identificar(foto, data.mesas_pba[ix], data.fiscales[0])
            identificar(foto, data.mesas_pba[ix], data.fiscales[1])
        elif (ix < 19):
            identificar(foto, data.mesas_caba[ix-14], data.fiscales[2])
            identificar(foto, data.mesas_caba[ix-14], data.fiscales[3])
        elif (ix < 21):
            identificar(foto, data.mesas_cat[ix-19], data.fiscales[4])
            identificar(foto, data.mesas_cat[ix-19], data.fiscales[5])
        elif (ix < 24):
            reportar_problema_attachment(foto, data.fiscales[6])
            reportar_problema_attachment(foto, data.fiscales[7])
        elif (ix < 30):
            identificar(foto, data.mesas_pba[ix-10], data.fiscales[8])

    consumir_novedades()
    generador = GeneradorDatosFotosDistrital(settings.DISTRITO_PBA)
    generador.calcular()

    assert generador.cantidad_mesas == 20
    assert generador.mesas_con_foto_identificada == 14



def test_datos_preidentificaciones(db, settings):
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2
    settings.DISTRITO_PBA = '2'

    # 50 mesas: 20 pba, 15 caba, 15 catamarca
    data = DataTresDistritos()

    # 20 preidentificaciones
    preidents_pba = [PreidentificacionFactory(distrito=data.distrito_pba) for ix in range(12)] 
    preidents_caba = [PreidentificacionFactory(distrito=data.distrito_caba) for ix in range(8)]

    # 40 fotos:
    # - 14 / 5 / 2 identificadas a mesas pba / caba / catamarca
    # - 3 con problemas
    # - 6 en proceso de identificación
    # - 10 sin acciones
    fotos = []
    for ix in range(40):
        foto = AttachmentFactory()
        fotos.append(foto)
        if (ix < 14):
            identificar(foto, data.mesas_pba[ix], data.fiscales[0])
            identificar(foto, data.mesas_pba[ix], data.fiscales[1])
            if (ix < 5):
                foto.pre_identificacion = preidents_pba[ix]
                foto.save(update_fields=['pre_identificacion'])
        elif (ix < 19):
            identificar(foto, data.mesas_caba[ix-14], data.fiscales[2])
            identificar(foto, data.mesas_caba[ix-14], data.fiscales[3])
            if (ix < 17):
                foto.pre_identificacion = preidents_caba[ix-14]
                foto.save(update_fields=['pre_identificacion'])
        elif (ix < 21):
            identificar(foto, data.mesas_cat[ix-19], data.fiscales[4])
            identificar(foto, data.mesas_cat[ix-19], data.fiscales[5])
        elif (ix < 24):
            reportar_problema_attachment(foto, data.fiscales[6])
            reportar_problema_attachment(foto, data.fiscales[7])
        elif (ix < 30):
            identificar(foto, data.mesas_pba[ix-10], data.fiscales[8])
            if (ix < 26):
                foto.pre_identificacion = preidents_pba[ix-19]
                foto.save(update_fields=['pre_identificacion'])
        elif (ix < 35):
            foto.pre_identificacion = preidents_pba[ix-23]
            foto.save(update_fields=['pre_identificacion'])
        elif (ix < 40):
            foto.pre_identificacion = preidents_caba[ix-32]
            foto.save(update_fields=['pre_identificacion'])

    consumir_novedades()
    generador_nacional = GeneradorDatosPreidentificaciones()
    generador_pba = GeneradorDatosPreidentificaciones(
        PreIdentificacion.objects.filter(distrito__numero=settings.DISTRITO_PBA))
    generador_nacional.calcular()
    generador_pba.calcular()

    assert generador_nacional.cantidad_total == 20
    assert generador_nacional.identificadas == 8
    assert generador_nacional.sin_identificar == 12
    assert generador_pba.cantidad_total == 12
    assert generador_pba.identificadas == 5
    assert generador_pba.sin_identificar == 7

