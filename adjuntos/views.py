from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.db import IntegrityError
from django.views.generic.edit import CreateView, FormView
from django.views.generic.base import View
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
from adjuntos.consolidacion import consolidar_identificaciones

MENSAJE_NINGUN_ATTACHMENT_VALIDO = 'Ningún archivo es válido'
MENSAJE_SOLO_UN_ACTA = 'Se debe subir una sola acta'

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


class IdentificacionCreateViewDesdeUnidadBasica(IdentificacionCreateView):

    template_name = "adjuntos/asignar-mesa-ub.html"

    def get_success_url(self):
        identificacion = self.object
        mesa_id = identificacion.mesa.id
        return reverse('procesar-acta-mesa', kwargs={'mesa_id': mesa_id})

    def form_valid(self, form):
        identificacion = form.save(commit=False)
        super().form_valid(form)
        #como viene desde una UB, consolidamos el attachment y ya le pasamos la mesa
        consolidar_identificaciones(identificacion.attachment, identificacion.mesa.id)
        return HttpResponseRedirect(self.get_success_url())


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
    agregar_adjuntos_url = 'agregar-adjuntos'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['url_to_post'] = self.get_url_to_post()
        return context


    def get_url_to_post(self):
        return self.agregar_adjuntos_url

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist('file_field')
        if form.is_valid():
            contador_fotos = 0
            for file in files:
                instance = self.procesar_adjunto(file)
                if instance is not None:
                    contador_fotos = contador_fotos + 1
            if contador_fotos:
                messages.success(self.request, f'Subiste {contador_fotos} imágenes de actas. Gracias!')
            return redirect(self.agregar_adjuntos_url)

        return self.form_invalid(form)


    def procesar_adjunto(self, adjunto):
        if adjunto.content_type not in ('image/jpeg', 'image/png'):
            messages.warning(self.request, f'{adjunto.name} ignorado. No es una imagen' )
            return None
        try:
            instance = Attachment(
                mimetype=adjunto.content_type
            )
            instance.foto.save(adjunto.name, adjunto, save=False)
            instance.save()
            return instance
        except IntegrityError:
            messages.warning(self.request, f'{adjunto.name} ya existe en el sistema' )
        return None

class AgregarAdjuntosDesdeUnidadBasica(AgregarAdjuntos):
    """
    Permite subir una imagen, genera la instancia de Attachment y debería redirigir al flujo de
    asignación de mesa -> carga de datos pp -> carga de datos secundarios , etc

    Si una imagen ya existe en el sistema, se exluye con un mensaje de error
    via `messages` framework.

    """

    form_class = AgregarAttachmentsForm

    def get_url_to_post(self):
        return 'agregar-adjuntos-ub'

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist('file_field')
        #no debiese poder cargarse por la ui dos imágenes, aunque es mejor poder chequear esto
        if len(files) > 1:
            form.add_error('file_field', MENSAJE_SOLO_UN_ACTA)

        if form.is_valid():
            file = files[0]
            instance = self.procesar_adjunto(file)
            if instance is not None:
                messages.success(self.request, 'Subiste el acta correctamente.')
                return redirect(reverse('asignar-mesa-ub', kwargs={"attachment_id": instance.id}))

            form.add_error('file_field', MENSAJE_NINGUN_ATTACHMENT_VALIDO)
        return self.form_invalid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'es_multiple': False})
        return kwargs

