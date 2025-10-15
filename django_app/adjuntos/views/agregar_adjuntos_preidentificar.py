from django.contrib import messages
from django.core.serializers import serialize

import structlog

from adjuntos.forms import (
    AgregarAttachmentsForm,
    IdentificacionForm,
    PreIdentificacionForm
)
from adjuntos.models import Attachment, Identificacion
from problemas.models import Problema
from .agregar_adjuntos import AgregarAdjuntos

logger = structlog.get_logger(__name__)


class AgregarAdjuntosPreidentificar(AgregarAdjuntos):
    """
    Permite subir varias imágenes pre identificándolas.

    Si una imagen ya existe en el sistema, se exluye con un mensaje de error
    via `messages` framework.
    """
    url_to_post = 'agregar-adjuntos'
    template_name = 'adjuntos/agregar-adjuntos-identificar.html'

    def get_context_data(self, **kwargs):
        context = super(AgregarAdjuntosPreidentificar, self).get_context_data(**kwargs)
        request = self.request
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
        context['attachment_form'] = AgregarAttachmentsForm()
        context['pre_identificacion_form'] = pre_identificacion_form
        return context

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
