import pytest

from elecciones.tests.factories import (
    MesaFactory, AttachmentFactory, PreidentificacionFactory,
    DistritoFactory, SeccionFactory, CircuitoFactory, LugarVotacionFactory,
    CategoriaFactory, MesaCategoriaFactory, CategoriaOpcionFactory,
    IdentificacionFactory, CargaFactory, VotoMesaReportadoFactory
)
from elecciones.tests.utils_para_test import (
    nuevo_fiscal, identificar, reportar_problema_attachment
)
from adjuntos.consolidacion import consumir_novedades
from elecciones.models import Mesa, Carga, MesaCategoria
from adjuntos.models import Attachment, PreIdentificacion
from elecciones.resultados_resumen import (
    GeneradorDatosFotosNacional, GeneradorDatosFotosDistrital, GeneradorDatosPreidentificaciones,
    GeneradorDatosCargaParcialConsolidado, GeneradorDatosCargaTotalConsolidado,
    SinRestriccion
)



def nueva_categoria(slug, nombres_opciones_prioritarias, nombres_opciones_no_prioritarias, distrito=None):
    categoria = CategoriaFactory(
        opciones=[], slug=slug, distrito=distrito) if distrito else CategoriaFactory(opciones=[], slug=slug)
    # sin opciones para crearlas ad hoc
    for nombre in nombres_opciones_prioritarias:
        CategoriaOpcionFactory(categoria=categoria, opcion__nombre=nombre, prioritaria=True)
    for nombre in nombres_opciones_no_prioritarias:
        CategoriaOpcionFactory(categoria=categoria, opcion__nombre=nombre, prioritaria=False)
    return categoria


def asociar_foto_a_mesa(mesa, data):
    foto = AttachmentFactory()
    IdentificacionFactory(
        status='identificada',
        attachment=foto,
        mesa=mesa,
        fiscal=data.fiscales[0]
    )
    IdentificacionFactory(
        status='identificada',
        attachment=foto,
        mesa=mesa,
        fiscal=data.fiscales[1]
    )


def nueva_carga(mesa_categoria, fiscal, votos_opciones, tipo_carga=Carga.TIPOS.total, origen=Carga.SOURCES.web):
    carga = CargaFactory(mesa_categoria=mesa_categoria, fiscal=fiscal, tipo=tipo_carga, origen=origen)
    for opcionVoto, cantidadVotos in zip(mesa_categoria.categoria.opciones.order_by('nombre'), votos_opciones):
        VotoMesaReportadoFactory(carga=carga, opcion=opcionVoto, votos=cantidadVotos)
    return carga


def agregar_cargas_mesa(mesacat, specs):
    print('acá van los specs')
    print(specs)
    print(specs[0])
    for ix in range(len(specs)):
        spec = specs[ix]
        nueva_carga(mesacat, spec.fiscales[ix], spec.votos(), spec.tipo_carga(), spec.origen())


class DataTresDistritos():
    def __init__(self, distrito_pba):
        self.distrito_caba = DistritoFactory(numero='1')
        self.seccion_caba = SeccionFactory(distrito=self.distrito_caba)
        self.circuito_caba = CircuitoFactory(seccion=self.seccion_caba)
        self.lugar_votacion_caba = LugarVotacionFactory(circuito=self.circuito_caba)
        self.distrito_pba = DistritoFactory(numero=distrito_pba)
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
        # votos por opción salvo excepciones, simplifica que haya doble carga coincidente


    def agregar_mesacats(self, settings):
        opciones_prioritarias = ["FT", "JC"]
        opciones_no_prioritarias = ["CF", "FIT", "Desp"]
        # presidente
        categoria_pv = nueva_categoria(
            settings.SLUG_CATEGORIA_PRESI_Y_VICE, opciones_prioritarias, opciones_no_prioritarias)
        self.mesacats_pv_pba = [MesaCategoriaFactory(
            mesa=mesa, categoria=categoria_pv) for mesa in self.mesas_pba]
        self.mesacats_pv_caba = [MesaCategoriaFactory(
            mesa=mesa, categoria=categoria_pv) for mesa in self.mesas_caba]
        self.mesacats_pv_cat = [MesaCategoriaFactory(
            mesa=mesa, categoria=categoria_pv) for mesa in self.mesas_cat]
        # gobernador PBA
        categoria_gv_pba = nueva_categoria(
            settings.SLUG_CATEGORIA_GOB_Y_VICE_PBA, opciones_prioritarias, opciones_no_prioritarias, self.distrito_pba)
        self.mesacats_gv_pba = [MesaCategoriaFactory(
            mesa=mesa, categoria=categoria_gv_pba) for mesa in self.mesas_pba]
        # una categoría CABA
        categoria_jefe_de_gobierno_caba = nueva_categoria(
            "JG_CABA", opciones_prioritarias, opciones_no_prioritarias, self.distrito_caba)
        self.mesacats_jg_caba = [MesaCategoriaFactory(
            mesa=mesa, categoria=categoria_jefe_de_gobierno_caba) for mesa in self.mesas_caba]
        # una categoría Catamarca
        categoria_diputados_catamarca = nueva_categoria(
            "DIP_CAT", opciones_prioritarias, opciones_no_prioritarias, self.distrito_cat)
        self.mesacats_jg_caba = [MesaCategoriaFactory(
            mesa=mesa, categoria=categoria_diputados_catamarca) for mesa in self.mesas_cat]

    def mesas(self):
        return self.mesas_pba + self.mesas_cat + self.mesas_caba


class Cargas():
    votos_totales = [40, 20, 2, 2, 2]
    votos_parciales = [40, 20]
    total_web = None
    total_csv = None
    parcial_web = None
    parcial_csv = None
    fiscales = None
    
    def __init__(self, tipo_carga, origen):
        self._tipo_carga = tipo_carga
        self._origen = origen

    def tipo_carga(self):
        return self._tipo_carga

    def origen(self):
        return self._origen

    def votos(self):
        return self.votos_totales if self.tipo_carga() == Carga.TIPOS.total else self.votos_parciales

    @classmethod
    def crear_cargas(cls):
        cls.total_web = Cargas(Carga.TIPOS.total, Carga.SOURCES.web)
        cls.total_csv = Cargas(Carga.TIPOS.total, Carga.SOURCES.csv)
        cls.parcial_web = Cargas(Carga.TIPOS.parcial, Carga.SOURCES.web)
        cls.parcial_csv = Cargas(Carga.TIPOS.parcial, Carga.SOURCES.csv)
        cls.fiscales = [nuevo_fiscal() for ix in range(10)]


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
    data = DataTresDistritos(settings.DISTRITO_PBA)

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
    data = DataTresDistritos(settings.DISTRITO_PBA)

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



def test_carga_datos(db, settings):
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2
    settings.MIN_COINCIDENCIAS_CARGAS = 2
    settings.MIN_COINCIDENCIAS_CARGAS_PROBLEMA = 1
    settings.DISTRITO_PBA = '2'
    settings.SLUG_CATEGORIA_PRESI_Y_VICE = 'PV'
    settings.SLUG_CATEGORIA_GOB_Y_VICE_PBA = 'GB_PBA'
    Cargas.crear_cargas()

    # 50 mesas: 20 pba, 15 caba, 15 catamarca
    data = DataTresDistritos(settings.DISTRITO_PBA)
    # agrego mesacats
    data.agregar_mesacats(settings)

    # cargo fotos para: 18 mesas PBA, 9 caba, 12 catamarca
    for mesa in data.mesas_pba[0:18]+data.mesas_caba[0:9]+data.mesas_cat[0:12]:
        asociar_foto_a_mesa(mesa, data)
    consumir_novedades()

    # Cargas PV - PBA
    # 1 total CSV + Web
    agregar_cargas_mesa(data.mesacats_pv_pba[0], [Cargas.total_csv, Cargas.total_web])
    # 1 doble carga total Web
    agregar_cargas_mesa(data.mesacats_pv_pba[1], [Cargas.parcial_web, Cargas.parcial_web, Cargas.total_web, Cargas.total_web])
    # 1 doble carga parcial + una carga total Web
    agregar_cargas_mesa(data.mesacats_pv_pba[2], [Cargas.parcial_web, Cargas.parcial_web, Cargas.total_web])
    # 3 doble carga Web (3-4-5)
    for ix in range(3):
        agregar_cargas_mesa(data.mesacats_pv_pba[ix+3], [Cargas.parcial_web, Cargas.parcial_web])
    # 2 carga total CSV (6-7)
    agregar_cargas_mesa(data.mesacats_pv_pba[6], [Cargas.total_csv])
    agregar_cargas_mesa(data.mesacats_pv_pba[7], [Cargas.total_csv])
    # 2 carga parcial CSV (8-9)
    agregar_cargas_mesa(data.mesacats_pv_pba[8], [Cargas.parcial_csv])
    agregar_cargas_mesa(data.mesacats_pv_pba[9], [Cargas.parcial_csv])
    # 3 carga parcial Web (10-11-12)
    agregar_cargas_mesa(data.mesacats_pv_pba[10], [Cargas.parcial_web])
    agregar_cargas_mesa(data.mesacats_pv_pba[11], [Cargas.parcial_web])
    agregar_cargas_mesa(data.mesacats_pv_pba[12], [Cargas.parcial_web])
    # 2 en conflicto (13-14)
    nueva_carga(data.mesacats_pv_pba[13], data.fiscales[2], Cargas.votos_parciales, Carga.TIPOS.parcial, Carga.SOURCES.web)
    nueva_carga(data.mesacats_pv_pba[13], data.fiscales[3], [
                n-1 for n in Cargas.votos_parciales], Carga.TIPOS.parcial, Carga.SOURCES.web)
    nueva_carga(data.mesacats_pv_pba[14], data.fiscales[2], Cargas.votos_parciales, Carga.TIPOS.parcial, Carga.SOURCES.web)
    nueva_carga(data.mesacats_pv_pba[14], data.fiscales[3], [
                n-1 for n in Cargas.votos_parciales], Carga.TIPOS.parcial, Carga.SOURCES.web)
    # 2 con problemas (15-16)
    nueva_carga(data.mesacats_pv_pba[15], data.fiscales[2], [], Carga.TIPOS.problema, Carga.SOURCES.web)
    nueva_carga(data.mesacats_pv_pba[16], data.fiscales[2], [], Carga.TIPOS.problema, Carga.SOURCES.web)

    # Cargas PV - CABA
    # 3 total CSV + Web (0-1-2)
    for ix in range(3):
        agregar_cargas_mesa(data.mesacats_pv_caba[ix], [Cargas.total_csv, Cargas.total_web])
    # 1 parcial CSV + Web (3)
    agregar_cargas_mesa(data.mesacats_pv_caba[3], [Cargas.parcial_csv, Cargas.parcial_web])
    # 1 doble carga parcial Web (4)
    agregar_cargas_mesa(data.mesacats_pv_caba[4], [Cargas.parcial_web, Cargas.parcial_web])
    # 2 carga parcial CSV (5-6)
    agregar_cargas_mesa(data.mesacats_pv_caba[5], [Cargas.parcial_csv])
    agregar_cargas_mesa(data.mesacats_pv_caba[6], [Cargas.parcial_csv])
    # 1 carga parcial Web (7)
    agregar_cargas_mesa(data.mesacats_pv_caba[7], [Cargas.parcial_web])
    # 1 en conflicto (8)
    nueva_carga(data.mesacats_pv_caba[8], data.fiscales[2],
                Cargas.votos_parciales, Carga.TIPOS.parcial, Carga.SOURCES.web)
    nueva_carga(data.mesacats_pv_caba[8], data.fiscales[3], [
                n-1 for n in Cargas.votos_parciales], Carga.TIPOS.parcial, Carga.SOURCES.web)

    # Cargas PV - Catamarca
    # 2 parcial CSV + Web (0-1)
    agregar_cargas_mesa(data.mesacats_pv_cat[0], [Cargas.parcial_csv, Cargas.parcial_web])
    agregar_cargas_mesa(data.mesacats_pv_cat[1], [Cargas.parcial_csv, Cargas.parcial_web])
    # 2 carga total CSV (2-3)
    agregar_cargas_mesa(data.mesacats_pv_cat[2], [Cargas.total_csv])
    agregar_cargas_mesa(data.mesacats_pv_cat[3], [Cargas.total_csv])
    # 2 carga parcial CSV (3-4)
    agregar_cargas_mesa(data.mesacats_pv_cat[4], [Cargas.parcial_csv])
    # 4 carga parcial Web (5-8)
    for ix in range(4):
        agregar_cargas_mesa(data.mesacats_pv_cat[ix+5], [Cargas.parcial_web])
    # 1 con problemas (9)
    nueva_carga(data.mesacats_pv_cat[9], data.fiscales[2], [], Carga.TIPOS.problema, Carga.SOURCES.web)

    # Cargas GV PBA
    # 1 total CSV + Web
    agregar_cargas_mesa(data.mesacats_gv_pba[0], [Cargas.total_csv, Cargas.total_web])
    # 1 parcial CSV + Web
    agregar_cargas_mesa(data.mesacats_gv_pba[1], [Cargas.parcial_csv, Cargas.parcial_web])
    # 2 doble carga total Web
    agregar_cargas_mesa(data.mesacats_gv_pba[2], [Cargas.parcial_web, Cargas.parcial_web, Cargas.total_web, Cargas.total_web])
    agregar_cargas_mesa(data.mesacats_gv_pba[3], [Cargas.parcial_web, Cargas.parcial_web, Cargas.total_web, Cargas.total_web])
    # 2 doble carga parcial + una carga total Web
    agregar_cargas_mesa(data.mesacats_gv_pba[4], [Cargas.parcial_web, Cargas.parcial_web, Cargas.total_web])
    agregar_cargas_mesa(data.mesacats_gv_pba[5], [Cargas.parcial_web, Cargas.parcial_web, Cargas.total_web])
    # 1 doble carga Web 
    agregar_cargas_mesa(data.mesacats_gv_pba[6], [Cargas.parcial_web, Cargas.parcial_web])
    # 1 carga total CSV 
    agregar_cargas_mesa(data.mesacats_gv_pba[7], [Cargas.total_csv])
    # 2 carga parcial CSV 
    agregar_cargas_mesa(data.mesacats_gv_pba[8], [Cargas.parcial_csv])
    agregar_cargas_mesa(data.mesacats_gv_pba[9], [Cargas.parcial_csv])
    # 5 carga parcial Web (10 a 14)
    for ix in range(5):
        agregar_cargas_mesa(data.mesacats_gv_pba[ix+10], [Cargas.parcial_web])
    # 1 en conflicto (15)
    nueva_carga(data.mesacats_gv_pba[15], data.fiscales[2], Cargas.votos_parciales, Carga.TIPOS.parcial, Carga.SOURCES.web)
    nueva_carga(data.mesacats_gv_pba[15], data.fiscales[3], [
                n-1 for n in Cargas.votos_parciales], Carga.TIPOS.parcial, Carga.SOURCES.web)

    consumir_novedades()

    # carga parcial - sobre total de mesas
    carga_parcial_todas_las_mesas = GeneradorDatosCargaParcialConsolidado(SinRestriccion(), None)
    carga_parcial_todas_las_mesas.calcular()
    # presidente y vice
    assert carga_parcial_todas_las_mesas.pv.dato_total == 50
    assert carga_parcial_todas_las_mesas.pv.dato_carga_confirmada == 13
    assert carga_parcial_todas_las_mesas.pv.dato_carga_csv == 9
    assert carga_parcial_todas_las_mesas.pv.dato_carga_en_proceso == 11
    assert carga_parcial_todas_las_mesas.pv.dato_carga_sin_carga == 14
    assert carga_parcial_todas_las_mesas.pv.dato_carga_con_problemas == 3
    # gobernador y vice PBA
    assert carga_parcial_todas_las_mesas.gv.dato_total == 20
    assert carga_parcial_todas_las_mesas.gv.dato_carga_confirmada == 7
    assert carga_parcial_todas_las_mesas.gv.dato_carga_csv == 3
    assert carga_parcial_todas_las_mesas.gv.dato_carga_en_proceso == 6
    assert carga_parcial_todas_las_mesas.gv.dato_carga_sin_carga == 4
    assert carga_parcial_todas_las_mesas.gv.dato_carga_con_problemas == 0

    # carga parcial - sobre mesas con fotos
    carga_parcial_todas_las_mesas.set_query_base(MesaCategoria.objects.exclude(mesa__attachments=None))
    carga_parcial_todas_las_mesas.calcular()
    # presidente y vice
    assert carga_parcial_todas_las_mesas.pv.dato_total == 39
    assert carga_parcial_todas_las_mesas.pv.dato_carga_confirmada == 13
    assert carga_parcial_todas_las_mesas.pv.dato_carga_csv == 9
    assert carga_parcial_todas_las_mesas.pv.dato_carga_en_proceso == 11
    assert carga_parcial_todas_las_mesas.pv.dato_carga_sin_carga == 3
    assert carga_parcial_todas_las_mesas.pv.dato_carga_con_problemas == 3
    # gobernador y vice PBA
    assert carga_parcial_todas_las_mesas.gv.dato_total == 18
    assert carga_parcial_todas_las_mesas.gv.dato_carga_confirmada == 7
    assert carga_parcial_todas_las_mesas.gv.dato_carga_csv == 3
    assert carga_parcial_todas_las_mesas.gv.dato_carga_en_proceso == 6
    assert carga_parcial_todas_las_mesas.gv.dato_carga_sin_carga == 2
    assert carga_parcial_todas_las_mesas.gv.dato_carga_con_problemas == 0

    # carga total - sobre total de mesas
    carga_total_todas_las_mesas = GeneradorDatosCargaTotalConsolidado(SinRestriccion(), None)
    carga_total_todas_las_mesas.calcular()
    # presidente y vice
    assert carga_total_todas_las_mesas.pv.dato_total == 50
    assert carga_total_todas_las_mesas.pv.dato_carga_confirmada == 5
    assert carga_total_todas_las_mesas.pv.dato_carga_csv == 4
    assert carga_total_todas_las_mesas.pv.dato_carga_en_proceso == 1
    assert carga_total_todas_las_mesas.pv.dato_carga_sin_carga == 37
    assert carga_total_todas_las_mesas.pv.dato_carga_con_problemas == 3
    # gobernador y vice PBA
    assert carga_total_todas_las_mesas.gv.dato_total == 20
    assert carga_total_todas_las_mesas.gv.dato_carga_confirmada == 3
    assert carga_total_todas_las_mesas.gv.dato_carga_csv == 1
    assert carga_total_todas_las_mesas.gv.dato_carga_en_proceso == 2
    assert carga_total_todas_las_mesas.gv.dato_carga_sin_carga == 14
    assert carga_total_todas_las_mesas.gv.dato_carga_con_problemas == 0

    # carga parcial - sobre mesas con fotos
    carga_total_todas_las_mesas.set_query_base(MesaCategoria.objects.exclude(mesa__attachments=None))
    carga_total_todas_las_mesas.calcular()
    # presidente y vice
    assert carga_total_todas_las_mesas.pv.dato_total == 39
    assert carga_total_todas_las_mesas.pv.dato_carga_confirmada == 5
    assert carga_total_todas_las_mesas.pv.dato_carga_csv == 4
    assert carga_total_todas_las_mesas.pv.dato_carga_en_proceso == 1
    assert carga_total_todas_las_mesas.pv.dato_carga_sin_carga == 26
    assert carga_total_todas_las_mesas.pv.dato_carga_con_problemas == 3
    # gobernador y vice PBA
    assert carga_total_todas_las_mesas.gv.dato_total == 18
    assert carga_total_todas_las_mesas.gv.dato_carga_confirmada == 3
    assert carga_total_todas_las_mesas.gv.dato_carga_csv == 1
    assert carga_total_todas_las_mesas.gv.dato_carga_en_proceso == 2
    assert carga_total_todas_las_mesas.gv.dato_carga_sin_carga == 12
    assert carga_total_todas_las_mesas.gv.dato_carga_con_problemas == 0
