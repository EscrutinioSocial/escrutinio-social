from elecciones.models import MesaCategoria, Carga, NIVELES_DE_AGREGACION

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
from elecciones.avance_carga import AvanceDeCarga
from adjuntos.consolidacion import (
    consumir_novedades_carga, consumir_novedades_identificacion
)


def nueva_categoria(nombres_opciones_prioritarias, nombres_opciones_no_prioritarias):
    categoria = CategoriaFactory(opciones=[])   # sin opciones para crearlas ad hoc
    for nombre in nombres_opciones_prioritarias:
        CategoriaOpcionFactory(categoria=categoria, opcion__nombre=nombre, prioritaria=True)
    for nombre in nombres_opciones_no_prioritarias:
        CategoriaOpcionFactory(categoria=categoria, opcion__nombre=nombre, prioritaria=False)
    return categoria


def crear_seccion(nombre):
    seccion = SeccionFactory(nombre=nombre)
    circuito = CircuitoFactory(seccion=seccion)
    lugar_votacion = LugarVotacionFactory(circuito=circuito)
    return [seccion, circuito, lugar_votacion]


def nuevo_fiscal():
    usuario = UserFactory()
    fiscal = FiscalFactory(user=usuario)
    return fiscal


def crear_mesas(lugares_votacion, categorias, cantidad):
    mesas_creadas = []
    for lugar_votacion in lugares_votacion:
        mesas_creadas.append([])
    for nro in range(cantidad):
        indice_lugar_votacion = 0
        for lugar_votacion in lugares_votacion:
            numero_nueva_mesa = indice_lugar_votacion*1000+nro+1
            nueva_mesa = MesaFactory(
                lugar_votacion=lugar_votacion, numero=str(numero_nueva_mesa), categorias=categorias)
            mesas_creadas[indice_lugar_votacion].append(nueva_mesa)
            indice_lugar_votacion += 1
    return mesas_creadas


def identificar(attach, mesa, fiscal):
    return IdentificacionFactory(
        status='identificada',
        attachment=attach,
        mesa=mesa,
        fiscal=fiscal
    )


def nueva_carga(mesa_categoria, fiscal, votos_opciones, tipo_carga=Carga.TIPOS.total, origen=Carga.SOURCES.web):
    carga = CargaFactory(mesa_categoria=mesa_categoria, fiscal=fiscal, tipo=tipo_carga, origen=origen)
    for opcionVoto, cantidadVotos in zip(mesa_categoria.categoria.opciones.order_by('nombre'), votos_opciones):
        VotoMesaReportadoFactory(carga=carga, opcion=opcionVoto, votos=cantidadVotos)
    return carga


def mesacat(mesa, categoria):
    return MesaCategoria.objects.filter(mesa=mesa, categoria=categoria).first()


def verificar_resultado(res, cant_mesas, cant_electores, porc_mesas, porc_electores):
    assert res.cantidad_mesas() == cant_mesas
    assert res.cantidad_electores() == cant_electores
    assert res.porcentaje_mesas() == porc_mesas
    assert res.porcentaje_electores() == porc_electores


def test_avance_de_carga_sencillo(db, settings):
    # settings
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2
    settings.MIN_COINCIDENCIAS_CARGA = 2

    # categoria con cuatro opciones, dos prioritarias, dos no prioritarias
    pv = nueva_categoria(["a1", "a2"], ["b1", "b2"])
    # 10 mesas de 100, 110, ..., 190 votantes. Total 1450
    seccion, circuito, lugar_votacion = crear_seccion("Luján oeste")
    [mesas] = crear_mesas([lugar_votacion], [pv], 10)
    for ix in range(len(mesas)):
        mesas[ix].electores = 100 + ix * 10
        mesas[ix].save(update_fields=['electores'])
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()

    # a siete mesas les hago identificación total, a una identificación parcial
    attachs = AttachmentFactory.create_batch(10)
    for ix in range(7):
        identificar(attachs[ix], mesas[ix], fiscal_1)
        identificar(attachs[ix], mesas[ix], fiscal_2)
    identificar(attachs[7], mesas[7], fiscal_1)
    consumir_novedades_identificacion()

    # primer carga parcial en tres mesas
    for ix in range(3):
        nueva_carga(mesacat(mesas[ix], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial)
    # a una de estas tres le mando una segunda carga coincidente
    nueva_carga(mesacat(mesas[0], pv), fiscal_2, [50, 30], Carga.TIPOS.parcial)
    consumir_novedades_carga()

    # estamos para probar
    vorwaerts = AvanceDeCarga()
    resultados = vorwaerts.get_resultados(pv)
    verificar_resultado(resultados.total(), 10, 1450, 100, 100)
    verificar_resultado(resultados.sin_identificar_sin_cargas(), 2, 370, 20, 25.52)
    verificar_resultado(resultados.en_identificacion_sin_cargas(), 1, 170, 10, 11.72)
    verificar_resultado(resultados.carga_parcial_sin_consolidar(), 2, 230, 20, 15.86)
    verificar_resultado(resultados.carga_parcial_consolidada_dc(), 1, 100, 10, 6.9)
    verificar_resultado(resultados.carga_total_sin_consolidar(), 0, 0, 0, 0)
    verificar_resultado(resultados.carga_total_consolidada_dc(), 0, 0, 0, 0)


def test_avance_de_carga_dos_categorias(db, settings):
    # settings
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2
    settings.MIN_COINCIDENCIAS_CARGA = 2

    # dos categoríasas con cuatro opciones, dos prioritarias, dos no prioritarias
    pv = nueva_categoria(["a1", "a2"], ["b1", "b2"])
    gv = nueva_categoria(["a1", "a2"], ["b1", "b2"])
    # 10 mesas de 100, 110, ..., 190 votantes. Total 1450
    seccion, circuito, lugar_votacion = crear_seccion("Luján oeste")
    [mesas] = crear_mesas([lugar_votacion], [pv, gv], 10)
    for ix in range(len(mesas)):
        mesas[ix].electores = 100 + ix * 10
        mesas[ix].save(update_fields=['electores'])
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()

    # identifico 9 mesas
    attachs = AttachmentFactory.create_batch(10)
    for ix in range(9):
        identificar(attachs[ix], mesas[ix], fiscal_1)
        identificar(attachs[ix], mesas[ix], fiscal_2)
    consumir_novedades_identificacion()

    # doble carga parcial coincidente de 6 mesas pv y 2 mesas gv
    for ix in range(6):
        nueva_carga(mesacat(mesas[ix], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial)
        nueva_carga(mesacat(mesas[ix], pv), fiscal_2, [50, 30], Carga.TIPOS.parcial)
    for ix in range(2):
        nueva_carga(mesacat(mesas[ix], gv), fiscal_1, [55, 25], Carga.TIPOS.parcial)
        nueva_carga(mesacat(mesas[ix], gv), fiscal_2, [55, 25], Carga.TIPOS.parcial)
    # una carga parcial de una mesa pv y tres gv
    nueva_carga(mesacat(mesas[6], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial)
    for ix in range(3):
        nueva_carga(mesacat(mesas[ix+2], gv), fiscal_1, [55, 25], Carga.TIPOS.parcial)
    consumir_novedades_carga()

    # resultados
    vorwaerts = AvanceDeCarga()
    # categoría pv
    resultados = vorwaerts.get_resultados(pv)
    verificar_resultado(resultados.total(), 10, 1450, 100, 100)
    verificar_resultado(resultados.sin_identificar_sin_cargas(), 1, 190, 10, 13.1)
    verificar_resultado(resultados.en_identificacion_sin_cargas(), 0, 0, 0, 0)
    verificar_resultado(resultados.sin_cargar(), 2, 350, 20, 24.14)
    verificar_resultado(resultados.carga_parcial_sin_consolidar(), 1, 160, 10, 11.03)
    verificar_resultado(resultados.carga_parcial_consolidada_dc(), 6, 750, 60, 51.72)
    # categoría gv
    resultados = vorwaerts.get_resultados(gv)
    verificar_resultado(resultados.total(), 10, 1450, 100, 100)
    verificar_resultado(resultados.sin_identificar_sin_cargas(), 1, 190, 10, 13.1)
    verificar_resultado(resultados.en_identificacion_sin_cargas(), 0, 0, 0, 0)
    verificar_resultado(resultados.sin_cargar(), 4, 660, 40, 45.52)
    verificar_resultado(resultados.carga_parcial_sin_consolidar(), 3, 390, 30, 26.9)
    verificar_resultado(resultados.carga_parcial_consolidada_dc(), 2, 210, 20, 14.48)


def test_avance_de_carga_dos_circuitos(db, settings):
    # settings
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2
    settings.MIN_COINCIDENCIAS_CARGA = 2

    # dos categorías con cuatro opciones, dos prioritarias, dos no prioritarias
    pv = nueva_categoria(["a1", "a2"], ["b1", "b2"])
    gv = nueva_categoria(["a1", "a2"], ["b1", "b2"])
    # un circuito con 10 mesas de 100, 110, ..., 190 votantes. Total 1450
    seccion_1, circuito_1, lugar_votacion_1 = crear_seccion("Luján oeste")
    [mesas_1] = crear_mesas([lugar_votacion_1], [pv, gv], 10)
    for ix in range(len(mesas_1)):
        mesas_1[ix].electores = 100 + ix * 10
        mesas_1[ix].save(update_fields=['electores'])
    # otro circuito con 20 mesas de 200 votantes. Total 4000
    seccion_2, circuito_2, lugar_votacion_2 = crear_seccion("Mercedes")
    [mesas_2] = crear_mesas([lugar_votacion_2], [pv, gv], 20)
    for ix in range(len(mesas_2)):
        mesas_2[ix].electores = 200
        mesas_2[ix].save(update_fields=['electores'])
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()

    # identifico todas las mesas salvo dos de la sección 2
    attachs = AttachmentFactory.create_batch(30)
    for ix in range(10):
        identificar(attachs[ix], mesas_1[ix], fiscal_1)
        identificar(attachs[ix], mesas_1[ix], fiscal_2)
    for ix in range(18):
        identificar(attachs[ix+10], mesas_2[ix], fiscal_1)
        identificar(attachs[ix+10], mesas_2[ix], fiscal_2)
    consumir_novedades_identificacion()

    # sección 1
    # doble carga parcial coincidente de 6 mesas pv y 2 mesas gv
    for ix in range(6):
        nueva_carga(mesacat(mesas_1[ix], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial)
        nueva_carga(mesacat(mesas_1[ix], pv), fiscal_2, [50, 30], Carga.TIPOS.parcial)
    for ix in range(2):
        nueva_carga(mesacat(mesas_1[ix], gv), fiscal_1, [55, 25], Carga.TIPOS.parcial)
        nueva_carga(mesacat(mesas_1[ix], gv), fiscal_2, [55, 25], Carga.TIPOS.parcial)
    # una carga parcial de una mesa pv y tres gv
    nueva_carga(mesacat(mesas_1[6], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial)
    for ix in range(3):
        nueva_carga(mesacat(mesas_1[ix+2], gv), fiscal_1, [55, 25], Carga.TIPOS.parcial)
    consumir_novedades_carga()

    # sección 2
    # doble carga parcial coincidente de 15 mesas pv y 12 gv
    for ix in range(15):
        nueva_carga(mesacat(mesas_2[ix], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial)
        nueva_carga(mesacat(mesas_2[ix], pv), fiscal_2, [50, 30], Carga.TIPOS.parcial)
    for ix in range(12):
        nueva_carga(mesacat(mesas_2[ix], gv), fiscal_1, [55, 25], Carga.TIPOS.parcial)
        nueva_carga(mesacat(mesas_2[ix], gv), fiscal_2, [55, 25], Carga.TIPOS.parcial)
    # una carga parcial 6 mesas gv
    for ix in range(6):
        nueva_carga(mesacat(mesas_2[ix+12], gv), fiscal_1, [55, 25], Carga.TIPOS.parcial)
    consumir_novedades_carga()

    # resultados circuito 1
    vorwaerts = AvanceDeCarga(NIVELES_DE_AGREGACION.circuito, [circuito_1.id])
    # categoría pv
    resultados = vorwaerts.get_resultados(pv)
    verificar_resultado(resultados.total(), 10, 1450, 100, 100)
    verificar_resultado(resultados.sin_identificar_sin_cargas(), 0, 0, 0, 0)
    verificar_resultado(resultados.sin_cargar(), 3, 540, 30, 37.24)
    verificar_resultado(resultados.carga_parcial_sin_consolidar(), 1, 160, 10, 11.03)
    verificar_resultado(resultados.carga_parcial_consolidada_dc(), 6, 750, 60, 51.72)
    # categoría gv
    resultados = vorwaerts.get_resultados(gv)
    verificar_resultado(resultados.total(), 10, 1450, 100, 100)
    verificar_resultado(resultados.sin_identificar_sin_cargas(), 0, 0, 0, 0)
    verificar_resultado(resultados.sin_cargar(), 5, 850, 50, 58.62)
    verificar_resultado(resultados.carga_parcial_sin_consolidar(), 3, 390, 30, 26.9)
    verificar_resultado(resultados.carga_parcial_consolidada_dc(), 2, 210, 20, 14.48)

    # resultados circuito 2
    vorwaerts = AvanceDeCarga(NIVELES_DE_AGREGACION.circuito, [circuito_2.id])
    # categoría pv
    resultados = vorwaerts.get_resultados(pv)
    verificar_resultado(resultados.total(), 20, 4000, 100, 100)
    verificar_resultado(resultados.sin_identificar_sin_cargas(), 2, 400, 10, 10)
    verificar_resultado(resultados.sin_cargar(), 3, 600, 15, 15)
    verificar_resultado(resultados.carga_parcial_sin_consolidar(), 0, 0, 0, 0)
    verificar_resultado(resultados.carga_parcial_consolidada_dc(), 15, 3000, 75, 75)
    # categoría gv
    resultados = vorwaerts.get_resultados(gv)
    verificar_resultado(resultados.total(), 20, 4000, 100, 100)
    verificar_resultado(resultados.sin_identificar_sin_cargas(), 2, 400, 10, 10)
    verificar_resultado(resultados.sin_cargar(), 0, 0, 0, 0)
    verificar_resultado(resultados.carga_parcial_sin_consolidar(), 6, 1200, 30, 30)
    verificar_resultado(resultados.carga_parcial_consolidada_dc(), 12, 2400, 60, 60)


def test_avance_de_carga_combinando_dc_y_csv(db, settings):
    # settings
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2
    settings.MIN_COINCIDENCIAS_CARGA = 2

    # una categoria con cuatro opciones, dos prioritarias, dos no prioritarias
    pv = nueva_categoria(["a1", "a2"], ["b1", "b2"])
    # un circuito con 20 mesas de 100, 110, ..., 290 votantes. Total 3900
    seccion_1, circuito_1, lugar_votacion_1 = crear_seccion("Luján oeste")
    [mesas_1] = crear_mesas([lugar_votacion_1], [pv], 20)
    for ix in range(len(mesas_1)):
        mesas_1[ix].electores = 100 + ix * 10
        mesas_1[ix].save(update_fields=['electores'])
    # dos fiscales
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()

    # identifico 18 mesas
    attachs = AttachmentFactory.create_batch(30)
    for ix in range(18):
        identificar(attachs[ix], mesas_1[ix], fiscal_1)
        identificar(attachs[ix], mesas_1[ix], fiscal_2)
    consumir_novedades_identificacion()

    # doble carga total coincidente de 4 mesas
    for ix in range(4):
        nueva_carga(mesacat(mesas_1[ix], pv), fiscal_1, [50, 30, 20, 10], Carga.TIPOS.total)
        nueva_carga(mesacat(mesas_1[ix], pv), fiscal_2, [50, 30, 20, 10], Carga.TIPOS.total)
    # cinco cargas totales desde CSV
    for ix in range(5):
        nueva_carga(mesacat(mesas_1[4+ix], pv), fiscal_1,
                    [50, 30, 20, 10], Carga.TIPOS.total, Carga.SOURCES.csv)
    # doble carga parcial coincidente de 3 mesas
    for ix in range(3):
        nueva_carga(mesacat(mesas_1[9+ix], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial)
        nueva_carga(mesacat(mesas_1[9+ix], pv), fiscal_2, [50, 30], Carga.TIPOS.parcial)
    # dos cargas parciales desde CSV
    nueva_carga(mesacat(mesas_1[12], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial, Carga.SOURCES.csv)
    nueva_carga(mesacat(mesas_1[13], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial, Carga.SOURCES.csv)
    # una carga parcial 
    nueva_carga(mesacat(mesas_1[14], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial)
    consumir_novedades_carga()

    # podemos mirar
    vorwaerts = AvanceDeCarga(NIVELES_DE_AGREGACION.circuito, [circuito_1.id])
    resultados = vorwaerts.get_resultados(pv)
    verificar_resultado(resultados.total(), 20, 3900, 100, 100)
    verificar_resultado(resultados.sin_identificar_sin_cargas(), 2, 570, 10, 14.62)
    verificar_resultado(resultados.sin_cargar(), 3, 780, 15, 20)
    verificar_resultado(resultados.carga_parcial_sin_consolidar(), 1, 240, 5, 6.15)
    verificar_resultado(resultados.carga_parcial_consolidada_csv(), 2, 450, 10, 11.54)
    verificar_resultado(resultados.carga_parcial_consolidada_dc(), 3, 600, 15, 15.38)
    verificar_resultado(resultados.carga_total_sin_consolidar(), 0, 0, 0, 0)
    verificar_resultado(resultados.carga_total_consolidada_csv(), 5, 800, 25, 20.51)
    verificar_resultado(resultados.carga_total_consolidada_dc(), 4, 460, 20, 11.79)


def test_avance_de_carga_identificacion_parcial(db, settings):
        # settings
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2
    settings.MIN_COINCIDENCIAS_CARGA = 2

    # una categoria con cuatro opciones, dos prioritarias, dos no prioritarias
    pv = nueva_categoria(["a1", "a2"], ["b1", "b2"])
    # un circuito con 10 mesas de 100, 110, ..., 290 votantes. Total 1450
    seccion_1, circuito_1, lugar_votacion_1 = crear_seccion("Luján oeste")
    [mesas_1] = crear_mesas([lugar_votacion_1], [pv], 10)
    for ix in range(len(mesas_1)):
        mesas_1[ix].electores = 100 + ix * 10
        mesas_1[ix].save(update_fields=['electores'])
    # dos fiscales
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()

    # identifico totalmente 5 mesas, parcialmente 2 más
    attachs = AttachmentFactory.create_batch(30)
    for ix in range(5):
        identificar(attachs[ix], mesas_1[ix], fiscal_1)
        identificar(attachs[ix], mesas_1[ix], fiscal_2)
    identificar(attachs[5], mesas_1[5], fiscal_1)
    identificar(attachs[6], mesas_1[6], fiscal_1)
    consumir_novedades_identificacion()

    # dos cargas parciales 
    nueva_carga(mesacat(mesas_1[0], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial)
    nueva_carga(mesacat(mesas_1[1], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial)
    consumir_novedades_carga()

    # podemos mirar
    vorwaerts = AvanceDeCarga(NIVELES_DE_AGREGACION.circuito, [circuito_1.id])
    resultados = vorwaerts.get_resultados(pv)
    verificar_resultado(resultados.total(), 10, 1450, 100, 100)
    verificar_resultado(resultados.sin_identificar_sin_cargas(), 3, 540, 30, 37.24)
    verificar_resultado(resultados.sin_identificar_con_cargas(), 0, 0, 0, 0)
    verificar_resultado(resultados.en_identificacion_sin_cargas(), 2, 310, 20, 21.38)
    verificar_resultado(resultados.en_identificacion_con_cargas(), 0, 0, 0, 0)
    verificar_resultado(resultados.sin_cargar(), 3, 390, 30, 26.9)
    verificar_resultado(resultados.carga_parcial_sin_consolidar(), 2, 210, 20, 14.48)
    verificar_resultado(resultados.carga_parcial_consolidada_csv(), 0, 0, 0, 0)
    verificar_resultado(resultados.carga_parcial_consolidada_dc(), 0, 0, 0, 0)
    verificar_resultado(resultados.carga_total_sin_consolidar(), 0, 0, 0, 0)
    verificar_resultado(resultados.carga_total_consolidada_csv(), 0, 0, 0, 0)
    verificar_resultado(resultados.carga_total_consolidada_dc(), 0, 0, 0, 0)


def test_avance_de_carga_mesas_con_carga_csv_sin_fotos(db, settings):
        # settings
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2
    settings.MIN_COINCIDENCIAS_CARGA = 2

    # una categoria con cuatro opciones, dos prioritarias, dos no prioritarias
    pv = nueva_categoria(["a1", "a2"], ["b1", "b2"])
    # un circuito con 10 mesas de 100, 110, ..., 290 votantes. Total 1450
    seccion_1, circuito_1, lugar_votacion_1 = crear_seccion("Luján oeste")
    [mesas_1] = crear_mesas([lugar_votacion_1], [pv], 10)
    for ix in range(len(mesas_1)):
        mesas_1[ix].electores = 100 + ix * 10
        mesas_1[ix].save(update_fields=['electores'])
    # dos fiscales
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()

    # identifico totalmente 6 mesas, parcialmente dos mesas
    attachs = AttachmentFactory.create_batch(30)
    for ix in range(6):
        identificar(attachs[ix], mesas_1[ix], fiscal_1)
        identificar(attachs[ix], mesas_1[ix], fiscal_2)
    identificar(attachs[6], mesas_1[6], fiscal_1)
    identificar(attachs[7], mesas_1[7], fiscal_1)
    consumir_novedades_identificacion()

    # dos cargas parciales
    nueva_carga(mesacat(mesas_1[0], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial)
    nueva_carga(mesacat(mesas_1[1], pv), fiscal_1, [50, 30], Carga.TIPOS.parcial)
    # tres cargas totales desde CSV de una mesa sin identificar (la última), una parcialmente identificada, una identificada
    nueva_carga(mesacat(mesas_1[9], pv), fiscal_1, [50, 30, 20, 10], Carga.TIPOS.total, Carga.SOURCES.csv)
    nueva_carga(mesacat(mesas_1[6], pv), fiscal_1, [50, 30, 20, 10], Carga.TIPOS.total, Carga.SOURCES.csv)
    nueva_carga(mesacat(mesas_1[2], pv), fiscal_1, [50, 30, 20, 10], Carga.TIPOS.total, Carga.SOURCES.csv)
    consumir_novedades_carga()

    # podemos mirar
    vorwaerts = AvanceDeCarga(NIVELES_DE_AGREGACION.circuito, [circuito_1.id])
    resultados = vorwaerts.get_resultados(pv)
    verificar_resultado(resultados.total(), 10, 1450, 100, 100)
    verificar_resultado(resultados.sin_identificar_sin_cargas(), 1, 180, 10, 12.41)
    verificar_resultado(resultados.sin_identificar_con_cargas(), 1, 190, 10, 13.1)
    verificar_resultado(resultados.en_identificacion_sin_cargas(), 1, 170, 10, 11.72)
    verificar_resultado(resultados.en_identificacion_con_cargas(), 1, 160, 10, 11.03)
    verificar_resultado(resultados.sin_cargar(), 3, 420, 30, 28.97)
    verificar_resultado(resultados.carga_parcial_sin_consolidar(), 2, 210, 20, 14.48)
    verificar_resultado(resultados.carga_parcial_consolidada_csv(), 0, 0, 0, 0)
    verificar_resultado(resultados.carga_parcial_consolidada_dc(), 0, 0, 0, 0)
    verificar_resultado(resultados.carga_total_sin_consolidar(), 0, 0, 0, 0)
    verificar_resultado(resultados.carga_total_consolidada_csv(), 3, 470, 30, 32.41)
    verificar_resultado(resultados.carga_total_consolidada_dc(), 0, 0, 0, 0)


def test_avance_de_carga_mesas_con_varias_fotos(db, settings):
        # settings
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2
    settings.MIN_COINCIDENCIAS_CARGA = 2

    # una categoria con cuatro opciones, dos prioritarias, dos no prioritarias
    pv = nueva_categoria(["a1", "a2"], ["b1", "b2"])
    # un circuito con 10 mesas de 100, 110, ..., 290 votantes. Total 1450
    seccion_1, circuito_1, lugar_votacion_1 = crear_seccion("Luján oeste")
    [mesas_1] = crear_mesas([lugar_votacion_1], [pv], 10)
    for ix in range(len(mesas_1)):
        mesas_1[ix].electores = 100 + ix * 10
        mesas_1[ix].save(update_fields=['electores'])
    # dos fiscales
    fiscal_1 = nuevo_fiscal()
    fiscal_2 = nuevo_fiscal()

    # identifico totalmente 5 mesas
    attachs = AttachmentFactory.create_batch(30)
    for ix in range(5):
        identificar(attachs[ix], mesas_1[ix], fiscal_1)
        identificar(attachs[ix], mesas_1[ix], fiscal_2)
    identificar(attachs[5], mesas_1[5], fiscal_1)
    identificar(attachs[6], mesas_1[6], fiscal_1)
    # agrego dos fotos más a la primer mesa
    identificar(attachs[7], mesas_1[0], fiscal_1)
    identificar(attachs[7], mesas_1[0], fiscal_2)
    identificar(attachs[8], mesas_1[0], fiscal_1)
    identificar(attachs[8], mesas_1[0], fiscal_2)
    # agrego otra foto parcial a la segunda mesa
    identificar(attachs[9], mesas_1[1], fiscal_1)
    # agrego una fotos más a la tercer mesa
    identificar(attachs[10], mesas_1[2], fiscal_1)
    identificar(attachs[10], mesas_1[2], fiscal_2)
    consumir_novedades_identificacion()
