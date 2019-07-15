from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from django.urls import reverse
from django.db import IntegrityError
from django.views.generic.edit import CreateView, FormView
from django.utils.decorators import method_decorator
from elecciones.views import StaffOnlyMixing
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils.functional import cached_property
import base64
from django.core.files.base import ContentFile
from django.views.decorators.csrf import csrf_exempt
from .models import Attachment, Identificacion
from .forms import (
    AgregarAttachmentsForm,
    IdentificacionForm,
    IdentificacionProblemaForm,
)


@login_required
def post_asignar_mesa(request, decision, contenido):
    contenido_para_mostrar = contenido if decision == "mesa" else contenido.replace("_", " ")
    return render(request, 'adjuntos/post-asignar-mesa.html', { 'decision': decision, 'contenido': contenido_para_mostrar })



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
        resultado = self.get_operation_result()
        return reverse('post-asignar-mesa', args=[resultado['decision'], resultado['contenido']])

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
    Si una imagen ya existe en el sistema, se exluye con un mensaje de error
    via `messages` framework.

    """

    form_class = AgregarAttachmentsForm
    template_name = 'adjuntos/agregar-adjuntos.html'
    success_url = 'agregada'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist('file_field')
        if form.is_valid():
            c = 0
            for f in files:
                if f.content_type not in ('image/jpeg', 'image/png'):
                    messages.warning(self.request, f'{f.name} ignorado. No es una imagen' )
                    continue

                try:
                    instance = Attachment(
                        mimetype=f.content_type
                    )
                    instance.foto.save(f.name, f, save=False)
                    instance.save()
                    c += 1
                except IntegrityError:
                    messages.warning(self.request, f'{f.name} ya existe en el sistema' )

            if c:
                messages.success(self.request, f'Subiste {c} imagenes de actas. Gracias!')
            return redirect('agregar-adjuntos')
        else:
            return self.form_invalid(form)
