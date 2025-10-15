from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
import structlog

from adjuntos.csv_import import CSVImporter
from adjuntos.forms import AgregarAttachmentsCSV
from .agregar_adjuntos import AgregarAdjuntos
from adjuntos.models import CSVTareaDeImportacion

logger = structlog.get_logger(__name__)

NO_PERMISSION_REDIRECT = 'permission-denied'

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


    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if request.user.fiscal.esta_en_grupo('unidades basicas'):
            return super().dispatch(request, *args, **kwargs)
        return HttpResponseForbidden()

    def cargar_informacion_adjunto(self, adjunto, subido_por, pre_identificacion, parent=None):
        try:
            tarea_importacion_csv = CSVTareaDeImportacion()
            tarea_importacion_csv.status = CSVTareaDeImportacion.STATUS.pendiente
            tarea_importacion_csv.fiscal = subido_por
            tarea_importacion_csv.csv_file = adjunto
            tarea_importacion_csv.save()
            url = reverse('status-importacion-csv', kwargs={'csv_id': tarea_importacion_csv.id})
            self.agregar_resultado_carga(
                messages.SUCCESS,
                f'{adjunto.name} importado. Podés ver su estado de procesamiento <a href="{url}">aquí</a>.'
            )
        except Exception as e:
            self.agregar_resultado_carga(
                messages.WARNING,
                f'{adjunto.name} no importado debido al siguiente error: {str(e)}'
            )
        return None

    def mostrar_mensaje_tipo_archivo_invalido(self, nombre_archivo):
        messages.warning(self.request, f'{nombre_archivo} ignorado. No es un archivo CSV.')

    def mostrar_mensaje_archivos_cargados(self, c):
        messages.success(self.request, f'Subiste {c} archivos CSV. Gracias!')


@login_required
@user_passes_test(
    lambda u: u.fiscal.esta_en_algun_grupo(['supervisores', 'unidades basicas']),
    login_url=NO_PERMISSION_REDIRECT
)
def status_importacion_csv(request, csv_id):
    fiscal = request.user.fiscal

    # Si es supervisor puede ver cualquier CSV. Si no, sólo los suyos.
    if fiscal.esta_en_grupo('supervisores'):
        tarea = get_object_or_404(CSVTareaDeImportacion, id=csv_id)
    else:
        tarea = get_object_or_404(CSVTareaDeImportacion, id=csv_id, fiscal=fiscal)

    context = {}
    context['csv_file'] = tarea.csv_file.name
    context['status'] = tarea.status
    context['ult_actualizacion'] = tarea.modified
    context['fiscal'] = tarea.fiscal
    context['mesas_total_ok'] = tarea.mesas_total_ok
    context['mesas_parc_ok'] = tarea.mesas_parc_ok

    resultados_carga = []

    # Muestro los errores.
    if tarea.errores:
        for error in tarea.errores.split('\n'):
            resultados_carga.append((messages.WARNING, f"{error}"))
    context['resultados_carga'] = resultados_carga
    return render(request, 'adjuntos/status-importacion-csv.html', context=context)
