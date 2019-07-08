from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from django.urls import reverse
from django.db import IntegrityError
from django.views.generic.edit import UpdateView, FormView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages

import base64
from django.core.files.base import ContentFile
from django.views.decorators.csrf import csrf_exempt

from adjuntos.csv_import import CSVImporter
from .models import Attachment
from .forms import AsignarMesaForm, AgregarAttachmentsForm


@login_required
def elegir_adjunto(request):
    """
    Elige un acta al azar del queryset :meth:`Attachment.sin asignar`,
    estampa el tiempo de "asignación" para que se excluya durante el periodo
    de guarda y redirige a la vista para la clasificación de la mesa elegida

    Si no hay más mesas sin asignar, se muestra un mensaje estático.
    """

    attachments = Attachment.sin_asignar()
    if attachments.exists():
        a = attachments.order_by('?').first()
        # se marca el adjunto
        a.taken = timezone.now()
        a.save(update_fields=['taken'])
        return redirect('asignar-mesa', attachment_id=a.id)

    return render(request, 'adjuntos/sin-actas.html')


class AsignarMesaAdjunto(UpdateView):
    """
    Esta es la vista que permite clasificar un acta,
    asociandola a una mesa o reportando un problema

    Ver :class:`adjuntos.forms.AsignarMesaForm`
    """

    form_class = AsignarMesaForm
    template_name = "adjuntos/asignar-mesa.html"
    pk_url_kwarg = 'attachment_id'
    model = Attachment

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_success_url(self):
        return reverse('elegir-adjunto')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['attachment'] = self.object
        context['button_tabindex'] = 2
        return context

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


@staff_member_required
@csrf_exempt
def editar_foto(request, attachment_id):
    """
    esta vista se invoca desde el plugin DarkRoom con el contenido
    de la imágen editada codificada en base64.

    Se decodifica y se guarda en el campo ``foto_edited``
    """
    attachment = get_object_or_404(Attachment, id=attachment_id)
    if request.method == 'POST' and request.POST['data']:
        data = request.POST['data']
        file_format, imgstr = data.split(';base64,')
        extension = file_format.split('/')[-1]
        attachment.foto_edited = ContentFile(base64.b64decode(imgstr), name=f'edited_{attachment_id}.{extension}')
        attachment.save(update_fields=['foto_edited'])
        return JsonResponse({'message': 'Imágen guardada'})
    return JsonResponse({'message': 'No se pudo guardar la imágen'})


class AgregarAdjuntos(FormView):
    """
    Permite subir una o más imágenes, generando instancias de ``Attachment``
    Si una imágen ya existe en el sistema, se excluye con un mensaje de error
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
        messages.warning(self.request, f'{f.name} ignorado. No es una imágen')


class AgregarAdjuntosImportados(AgregarAdjuntos):
    """
    Permite subir un csv y validar la info que contiene

    """

    def __init__(self):
        super().__init__(template="agregar-adjuntos-csv", types='text/csv')

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def procesar_archivo(self, file):
        # validar la info del archivo
        try:
            CSVImporter().validar_archivo(file)
            return 1
        except Exception as e:
            messages.error(self.request, f'{file.name} ignorado. {str(e)}')
        return 0

    def mostrar_mensaje_tipo_archivo_invalido(self, f):
        messages.warning(self.request, f'{f.name} ignorado. No es un archivo CSV')

    def mostrar_mensaje_archivos_cargados(self, c):
        messages.success(self.request, f'Subiste {c} archivos de actas. Gracias!')