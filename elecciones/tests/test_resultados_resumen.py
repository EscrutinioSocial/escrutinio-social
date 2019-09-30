import pytest

from elecciones.tests.factories import (
    MesaFactory, AttachmentFactory, PreidentificacionFactory
)
from elecciones.tests.utils_para_test import (
    nuevo_fiscal, identificar, reportar_problema_attachment
)
from adjuntos.consolidacion import consumir_novedades
from elecciones.models import Mesa
from adjuntos.models import Attachment
from elecciones.resultados_resumen import GeneradorDatosFotosNacional


def test_datos_fotos_nacional(db, settings):
    settings.MIN_COINCIDENCIAS_IDENTIFICACION = 2

    fiscales = [nuevo_fiscal() for ix in range(10)]
    mesas = [MesaFactory() for ix in range(30)]

    assert Mesa.objects.count() == 30
    assert Attachment.objects.count() == 0

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

    # 11 preidentificaciones
    for ix in range(11):
        PreidentificacionFactory()

    consumir_novedades()
    generador = GeneradorDatosFotosNacional()
    generador.calcular()

    assert generador.cantidad_mesas == 30
    assert generador.mesas_con_foto_identificada == 9
    assert generador.fotos_con_problema_confirmado == 1
    assert generador.fotos_en_proceso == 8
    assert generador.fotos_sin_acciones == 7
    assert generador.mesas_sin_foto == 5
    assert generador.preidendificaciones == 11


