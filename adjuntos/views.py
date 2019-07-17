import base64

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.edit import CreateView, FormView

from adjuntos.csv_import import CSVImporter
from .forms import (
    AgregarAttachmentsForm,
    IdentificacionForm,
    IdentificacionProblemaForm,
)
from .models import Attachment
from .models import Identificacion


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
        #result = get_operation_result(self)
        return reverse('siguiente-accion')

    def identificacion(self):
        # redefinido en IdentificacionProblemaCreateView donde la identificacion se maneja distinto
        return self.object

    def get_operation_result(self):
        if self.identificacion().mesa is None:
            return {'decision': 'problema', 'contenido': self.identificacion().status.replace(" ", "_")}
        else:
            return {'decision': 'mesa', 'contenido': self.identificacion().mesa.numero}

    @cached_property
    def attachment(self):
        return get_object_or_404(
            Attachment, id=self.kwargs['attachment_id']
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['attachment'] = self.attachment
        context['form_problema'] = IdentificacionProblemaForm()
        return context

    def form_valid(self, form):
        identificacion = form.save(commit=False)
        identificacion.status = Identificacion.STATUS.identificada
        identificacion.fiscal = self.request.user.fiscal
        identificacion.attachment = self.attachment
        identificacion.save()
        messages.info(
            self.request,
            f'Identificada mesa Nº {identificacion.mesa} - Circuito {identificacion.mesa.circuito}',
        )
        return super().form_valid(form)


class IdentificacionProblemaCreateView(IdentificacionCreateView):
    http_method_names = ['post']
    form_class = IdentificacionProblemaForm
    identificacion_creada = None

    def form_valid(self, form):
        identificacion = form.save(commit=False)
        identificacion.attachment = self.attachment
        identificacion.fiscal = self.request.user.fiscal
        identificacion.save()
        self.identificacion_creada = identificacion
        messages.info(
            self.request,
            f'Guardado como "{identificacion.get_status_display()}"',
        )
        return redirect(self.get_success_url())

    def identificacion(self):
        return self.identificacion_creada


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
        attachment.foto_edited = ContentFile(base64.b64decode(imgstr), name=f'edited_{attachment_id}.{extension}')
        attachment.save(update_fields=['foto_edited'])
        return JsonResponse({'message': 'Imagen guardada'})
    return JsonResponse({'message': 'No se pudo guardar la imagen'})


class AgregarAdjuntos(FormView):
    """
    Permite subir una o más imágenes, generando instancias de ``Attachment``
    Si una imagen ya existe en el sistema, se excluye con un mensaje de error
    via `messages` framework.

    """

    def __init__(self, template="agregar-adjuntos", types=('image/jpeg', 'image/png'), **kwargs):
        super().__init__(**kwargs)
        self.form_class = AgregarAttachmentsForm
        self.template = template
        self.template_name = 'adjuntos/' + template + '.html'
        self.types = types

    success_url = 'agregada'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def procesar_archivo(self, file):
        try:
            instance = Attachment(
                mimetype=file.content_type
            )
            instance.foto.save(file.name, file, save=False)
            instance.save()
            return 1
        except IntegrityError:
            messages.warning(self.request, f'{file.name} ya existe en el sistema')
            return 0

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist('file_field')
        if form.is_valid():
            c = 0
            for f in files:
                if f.content_type not in self.types:
                    self.mostrar_mensaje_tipo_archivo_invalido(f)
                    continue
                c += self.procesar_archivo(f)

            if c:
                self.mostrar_mensaje_archivos_cargados(c)
            return redirect(self.template)
        else:
            return self.form_invalid(form)

    def mostrar_mensaje_archivos_cargados(self, c):
        messages.success(self.request, f'Subiste {c} imagenes de actas. Gracias!')

    def mostrar_mensaje_tipo_archivo_invalido(self, f):
        messages.warning(self.request, f'{f.name} ignorado. No es una imagen')


class AgregarAdjuntosImportados(AgregarAdjuntos):
    """
    Permite subir un csv y validar la info que contiene

    """

    def __init__(self):
        super().__init__(template="agregar-adjuntos-csv", types='text/csv')

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if request.user.fiscal.esta_en_grupo('unidades basicas'):
            return super().dispatch(request, *args, **kwargs)
        return HttpResponseForbidden()


    def procesar_archivo(self, file):
        # validar la info del archivo
        try:
            CSVImporter(file, self.request.user).procesar()
            return 1
        except Exception as e:
            messages.error(self.request, f'{file.name} ignorado. {str(e)}')
        return 0

    def mostrar_mensaje_tipo_archivo_invalido(self, f):
        messages.warning(self.request, f'{f.name} ignorado. No es un archivo CSV')

    def mostrar_mensaje_archivos_cargados(self, c):
        messages.success(self.request, f'Subiste {c} archivos de actas. Gracias!')