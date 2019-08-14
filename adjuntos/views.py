import base64

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.edit import CreateView, FormView
from django.core.serializers import serialize
from django.conf import settings
from django.db import transaction

from sentry_sdk import capture_message
import structlog

from adjuntos.consolidacion import consolidar_identificaciones
from adjuntos.csv_import import CSVImporter
from .forms import (
    AgregarAttachmentsForm,
    IdentificacionForm,
    PreIdentificacionForm,
)
from .models import Attachment, Identificacion
from problemas.models import Problema
from problemas.forms import IdentificacionDeProblemaForm
from .forms import AgregarAttachmentsCSV

logger = structlog.get_logger(__name__)


MENSAJE_NINGUN_ATTACHMENT_VALIDO = 'Ningún archivo es válido o nuevo.'
MENSAJE_SOLO_UN_ACTA = 'Se debe subir una sola acta.'
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


class IdentificacionCreateView(CreateView):
    """
    Esta es la vista que permite clasificar un acta,
    asociándola a una mesa o reportando un problema

    Ver :class:`adjuntos.forms.IdentificacionForm`
    """
    form_class = IdentificacionForm
    template_name = "adjuntos/asignar-mesa.html"
    model = Identificacion

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        response = super().dispatch(*args, **kwargs)
        return response

    def get_success_url(self):
        return reverse('siguiente-accion')

    def identificacion(self):
        return self.object

    def get_operation_result(self):
        if self.identificacion().mesa is None:
            return {'decision': 'problema', 'contenido': self.identificacion().status.replace(" ", "_")}
        else:
            return {'decision': 'mesa', 'contenido': self.identificacion().mesa.numero}

    @property
    def attachment(self):
        attachment = get_object_or_404(Attachment, id=self.kwargs['attachment_id'])
        fiscal = self.request.user.fiscal
        # Sólo el fiscal asignado al attachment puede identificar la foto.
        if fiscal.attachment_asignado != attachment:
            capture_message(
                f"""
                Intento de asignar mesa de attachment {attachment.id} sin permiso.

                attachment: {attachment.id}
                fiscal: {fiscal} ({fiscal.id}, tenía asignada: {fiscal.attachment_asignado})
                """
            )
            # TO DO: deberíamos sumar puntos al score anti-trolling?
            # Lo mandamos nuevamente a que se le dé algo para hacer.
            raise reverse('siguiente-accion')
        return attachment

    def get_initial(self):
        initial = super(CreateView, self).get_initial()
        pre_identificacion = self.attachment.pre_identificacion
        if pre_identificacion is None:
            return initial
        if pre_identificacion.distrito is not None:
            initial['distrito'] = pre_identificacion.distrito
        if pre_identificacion.seccion is not None:
            initial['seccion'] = pre_identificacion.seccion.numero
        if pre_identificacion.circuito is not None:
            initial['circuito'] = pre_identificacion.circuito.numero
        return initial

    def get(self, *args, **kwargs):
        logger.info('inicio identificacion', id=self.attachment.id)
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(IdentificacionCreateView, self).get_context_data(**kwargs)
        context['attachment'] = self.attachment
        context['recibir_problema'] = 'asignar-problema'
        context['dato_id'] = self.attachment.id
        context['form_problema'] = IdentificacionDeProblemaForm()
        context['url_video_instructivo'] = settings.URL_VIDEO_INSTRUCTIVO
        return context

    def form_invalid(self, form):
        logger.info('error identificacion', id=self.attachment.id)
        return super().form_invalid(form)

    @transaction.atomic
    def form_valid(self, form):
        identificacion = form.save(commit=False)
        identificacion.status = Attachment.STATUS.identificada
        identificacion.fiscal = self.request.user.fiscal
        identificacion.attachment = self.attachment
        identificacion.save()
        attachment.desasignar_a_fiscal()  # Le bajamos la cuenta.
        messages.info(
            self.request,
            f'Identificada mesa Nº {identificacion.mesa} - circuito {identificacion.mesa.circuito}',
        )
        logger.info('fin identificación', id=self.attachment.id)
        return super().form_valid(form)


class IdentificacionCreateViewDesdeUnidadBasica(IdentificacionCreateView):
    template_name = "adjuntos/asignar-mesa-ub.html"

    def get_success_url(self):
        identificacion = self.object
        mesa_id = identificacion.mesa.id
        return reverse('procesar-acta-mesa', kwargs={'mesa_id': mesa_id})

    @transaction.atomic
    def form_valid(self, form):
        identificacion = form.save(commit=False)
        identificacion.source = Identificacion.SOURCES.csv
        identificacion.fiscal = self.request.user.fiscal
        super().form_valid(form)
        attachment.desasignar_a_fiscal()
        # Como viene desde una UB, consolidamos el attachment y ya le pasamos la mesa
        consolidar_identificaciones(identificacion.attachment)
        return redirect(self.get_success_url())


class ReporteDeProblemaCreateView(FormView):
    http_method_names = ['post']
    form_class = IdentificacionDeProblemaForm
    template_name = "problemas/problema.html"

    @cached_property
    def attachment(self):
        return get_object_or_404(Attachment, id=self.kwargs['attachment_id'])

    def form_invalid(self, form):
        tipo = bool(form.errors.get('tipo_de_problema', False))
        descripcion = bool(form.errors.get('descripcion', False))
        return JsonResponse({'problema_tipo': tipo, 'problema_descripcion': descripcion}, status=500)

    def form_valid(self, form):
        # por algun motivo seguramente espantoso, pasa dos veces por acá
        # una vez desde el POST ajax, y otra luego de la primer redirección
        # meto este hack para que sólo cree el objeto cuando es ajax
        # y en la segunda vuelta sólo redireccion
        if self.request.is_ajax():
            fiscal = self.request.user.fiscal
            # Lo falso grabo para quedarme con la data de sus campos.
            reporte_de_problema = form.save(commit=False)
            tipo_de_problema = reporte_de_problema.tipo_de_problema
            descripcion = reporte_de_problema.descripcion

            # Creo la identificación.
            identificacion = Identificacion.objects.create(
                status=Identificacion.STATUS.problema, fiscal=fiscal, mesa=None, attachment=self.attachment
            )
            # Creo el problema asociado.
            Problema.reportar_problema(fiscal, descripcion, tipo_de_problema, identificacion=identificacion)
            return JsonResponse({'status': 'hack'})
        # acá sólo va a llegar la segunda vez
        messages.info(
            self.request,
            f'Gracias por el reporte. Ahora pasamos a la siguiente acta.',
            extra_tags="problema"
        )
        return redirect('siguiente-accion')


@staff_member_required
@csrf_exempt
def editar_foto(request, attachment_id):
    """
    esta vista se invoca desde el plugin DarkRoom con el contenido
    de la imagen editada codificada en base64.

    Se decodifica y se guarda en el campo ``foto_edited``
    """
    attachment = get_object_or_404(Attachment, id=attachment_id)
    if request.method == 'POST' and request.POST['data']:
        data = request.POST['data']
        file_format, imgstr = data.split(';base64,')
        extension = file_format.split('/')[-1]
        attachment.foto_edited = ContentFile(
            base64.b64decode(imgstr), name=f'edited_{attachment_id}.{extension}'
        )
        logger.info('foto editada', id=attachment.id)
        attachment.save(update_fields=['foto_edited'])
        return JsonResponse({'message': 'Imagen guardada'})
    return JsonResponse({'message': 'No se pudo guardar la imagen'})


class AgregarAdjuntos(FormView):
    """
    Permite subir una o más imágenes, generando instancias de ``Attachment``
    Si una imagen ya existe en el sistema, se exluye con un mensaje de error
    via `messages` framework.
    """

    def __init__(self, types=('image/jpeg', 'image/png'), **kwargs):
        super().__init__(**kwargs)
        self.types = types

    form_class = AgregarAttachmentsForm

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['url_to_post'] = reverse(self.url_to_post)
        return context

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist('file_field')
        pre_identificacion = kwargs.get('pre_identificacion', None)
        if form.is_valid():
            contador_fotos = 0
            for file in files:
                instance = self.procesar_adjunto(file, request.user.fiscal, pre_identificacion)
                if instance is not None:
                    contador_fotos = contador_fotos + 1
            if contador_fotos:
                self.mostrar_mensaje_archivos_cargados(contador_fotos)
            return redirect(reverse(self.url_to_post))

        return self.form_invalid(form)

    def procesar_adjunto(self, adjunto, subido_por, pre_identificacion=None):
        if adjunto.content_type not in self.types:
            self.mostrar_mensaje_tipo_archivo_invalido(adjunto.name)
            return None
        return self.cargar_informacion_adjunto(adjunto, subido_por, pre_identificacion)

    def cargar_informacion_adjunto(self, adjunto, subido_por, pre_identificacion=None):
        try:
            instance = Attachment(mimetype=adjunto.content_type)
            instance.foto.save(adjunto.name, adjunto, save=False)
            instance.subido_por = subido_por
            if pre_identificacion is not None:
                instance.pre_identificacion = pre_identificacion
            instance.save()
            return instance
        except IntegrityError:
            messages.warning(
                self.request, (
                    f'El archivo {adjunto.name} ya fue subido con anterioridad. <br>'
                    'Verificá si era el que querías subir y, si lo era, '
                    'no tenés que hacer nada.<br> ¡Gracias!'
                ),
                extra_tags='safe'
            )
        return None

    def mostrar_mensaje_archivos_cargados(self, contador):
        messages.success(self.request, f'Subiste {contador} imágenes de actas. Gracias!')

    def mostrar_mensaje_tipo_archivo_invalido(self, nombre_archivo):
        messages.warning(self.request, f'{nombre_archivo} ignorado. No es una imagen')


class AgregarAdjuntosDesdeUnidadBasica(AgregarAdjuntos):
    """
    Permite subir una imagen, genera la instancia de Attachment y debería redirigir al flujo de
    asignación de mesa -> carga de datos pp -> carga de datos secundarios , etc

    Si una imagen ya existe en el sistema, se exluye con un mensaje de error
    via `messages` framework.
    """
    form_class = AgregarAttachmentsForm
    url_to_post = 'agregar-adjuntos-ub'
    template_name = 'adjuntos/agregar-adjuntos.html'

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        pre_identificacion_form = PreIdentificacionForm(self.request.POST)
        files = request.FILES.getlist('file_field')

        # No debería poder cargarse por UI más de una imagen, pero por las dudas lo chequeamos.

        if len(files) > 1:
            form.add_error('file_field', MENSAJE_SOLO_UN_ACTA)

        if form.is_valid():
            file = files[0]
            fiscal = request.user.fiscal
            with transaction.atomic():
                instance = self.procesar_adjunto(file, fiscal)
                if instance is not None:
                    messages.success(self.request, 'Subiste el acta correctamente.')
                    fiscal.asignar_attachment(instance)
                    instance.asignar_a_fiscal()
                    return redirect(reverse('asignar-mesa-ub', kwargs={"attachment_id": instance.id}))

            form.add_error('file_field', MENSAJE_NINGUN_ATTACHMENT_VALIDO)
        return self.form_invalid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'es_multiple': False})
        return kwargs


class AgregarAdjuntosPreidentificar(AgregarAdjuntos):
    """
    Permite subir varias imágenes pre identificándolas.

    Si una imagen ya existe en el sistema, se exluye con un mensaje de error
    via `messages` framework.
    """
    url_to_post = 'agregar-adjuntos'
    template_name = 'adjuntos/agregar-adjuntos-identificar.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        attachment_form = AgregarAttachmentsForm()
        initial = {}
        if request.user:
            fiscal = request.user.fiscal
            if fiscal.seccion:
                # Si el fiscal tiene una sección precargada tomamos los datos de ahí.
                initial['seccion'] = fiscal.seccion
                initial['distrito'] = fiscal.seccion.distrito
            elif fiscal.distrito:
                # Si no tiene sección, pero sí un distrito, vamos con eso.
                initial['distrito'] = fiscal.distrito
        pre_identificacion_form = PreIdentificacionForm(initial=initial)
        context['attachment_form'] = attachment_form
        context['pre_identificacion_form'] = pre_identificacion_form

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        form_class = AgregarAttachmentsForm
        form = self.get_form(form_class)
        pre_identificacion_form = PreIdentificacionForm(self.request.POST)
        files = request.FILES.getlist('file_field')

        if form.is_valid() and pre_identificacion_form.is_valid():

            fiscal = request.user.fiscal
            pre_identificacion = pre_identificacion_form.save(commit=False)
            pre_identificacion.fiscal = fiscal
            pre_identificacion.save()
            kwargs.update({'pre_identificacion': pre_identificacion})
            return super().post(request, *args, **kwargs)

        if not pre_identificacion_form.is_valid():
            messages.warning(self.request, f'Hubo algún error en la identificación. No se subió ningún archivo.')

        return self.form_invalid(form, pre_identificacion_form, **kwargs)

    def form_invalid(self, attachment_form, pre_identificacion_form, **kwargs):
        context = self.get_context_data()
        context['attachment_form'] = attachment_form
        context['pre_identificacion_form'] = pre_identificacion_form
        context['desde_ub'] = True
        return self.render_to_response(context)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'es_multiple': True})
        return kwargs


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
        # Valida la info del archivo.
        try:
            CSVImporter(adjunto, self.request.user).procesar()
            return 'success'
        except Exception as e:
            messages.error(self.request, f'{adjunto.name} ignorado. {str(e)}')
        return None

    def mostrar_mensaje_tipo_archivo_invalido(self, nombre_archivo):
        messages.warning(self.request, f'{nombre_archivo} ignorado. No es un archivo CSV')

    def mostrar_mensaje_archivos_cargados(self, c):
        messages.success(self.request, f'Subiste {c} archivos CSV. Gracias!')

