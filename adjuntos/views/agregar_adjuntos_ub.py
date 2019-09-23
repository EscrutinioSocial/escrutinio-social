from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.core.serializers import serialize
from django.db import transaction

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

MENSAJE_NINGUN_ATTACHMENT_VALIDO = 'Ningún archivo es válido o nuevo.'
MENSAJE_SOLO_UN_ACTA = 'Se debe subir una sola acta.'

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
