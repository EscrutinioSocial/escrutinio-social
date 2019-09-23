from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.core.serializers import serialize

import structlog

from adjuntos.csv_import import CSVImporter
from adjuntos.forms import (
    IdentificacionForm,
    AgregarAttachmentsCSV
)
from adjuntos.models import Attachment, Identificacion
from problemas.models import Problema
from .agregar_adjuntos import AgregarAdjuntos

logger = structlog.get_logger(__name__)

CSV_MIMETYPES = (
    'application/csv.ms-excel',
    'application/csv.msexcel',
    'application/csv',
    'text/csv',
    'text/plain',
    'application/vnd.ms-excel',
    'application/x-csv',
    'text/comma-separated-values',
    'text/x-comma-separated-values',
)

class AgregarAdjuntosCSV(AgregarAdjuntos):
    """
    Permite subir un archivo CSV, valida que posea todas las columnas necesarias y que los datos sean
    Válidos. Si las validaciones resultan OK, crear la información correspondiente en la base de datos:
    Cargas totales, parciales e instancias de votos.

    """
    form_class = AgregarAttachmentsCSV
    template_name = 'adjuntos/agregar-adjuntos-csv.html'
    url_to_post = 'agregar-adjuntos-csv'

    def __init__(self):
        super().__init__(types=CSV_MIMETYPES)

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if request.user.fiscal.esta_en_grupo('unidades basicas'):
            return super().dispatch(request, *args, **kwargs)
        return HttpResponseForbidden()

    def cargar_informacion_adjunto(self, adjunto, subido_por, pre_identificacion):
        messages.add_message(self.request, messages.INFO, f"Procesando {adjunto.name}, aguarde por favor...")
        try:
            cant_mesas_ok, cant_mesas_parcialmente_ok, errores = CSVImporter(adjunto, self.request.user).procesar()
            self.agregar_resultado_carga(
                messages.SUCCESS if cant_mesas_ok > 0 else messages.INFO,
               f"➡️ El archivo <b>{adjunto.name}</b> ingresó <b>{cant_mesas_ok}</b> mesas sin problemas,")
            self.agregar_resultado_carga(
                messages.SUCCESS if cant_mesas_parcialmente_ok > 0 else messages.INFO,
                f"&nbsp;<b>{cant_mesas_parcialmente_ok}</b> ingresaron alguna categoría")
            if errores:
                self.agregar_resultado_carga(
                    messages.INFO,
                    "&nbsp;y produjo <b>los siguientes errores</b>:")
                for error in errores.split('\n'):
                    self.agregar_resultado_carga(messages.WARNING, f"&nbsp;&nbsp;{error}")
        except Exception as e:
            self.agregar_resultado_carga(messages.WARNING,
                f'{adjunto.name} no importado debido al siguiente error: {str(e)}')
        return None

    def mostrar_mensaje_tipo_archivo_invalido(self, nombre_archivo):
        messages.warning(self.request, f'{nombre_archivo} ignorado. No es un archivo CSV.')

    def mostrar_mensaje_archivos_cargados(self, c):
        messages.success(self.request, f'Subiste {c} archivos CSV. Gracias!')
