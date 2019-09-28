from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic.edit import CreateView
from django.core.serializers import serialize
from django.conf import settings
from django.db import transaction

from sentry_sdk import capture_message
import structlog

from adjuntos.forms import IdentificacionForm
from adjuntos.models import Attachment, Identificacion
from problemas.models import Problema
from problemas.forms import IdentificacionDeProblemaForm

logger = structlog.get_logger(__name__)

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

        return attachment

    def get_initial(self):
        initial = super(CreateView, self).get_initial()
        pre_identificacion = self.attachment.pre_identificacion
        if pre_identificacion is None:
            return initial
        if pre_identificacion.distrito is not None:
            initial['distrito'] = pre_identificacion.distrito
            # Sólo vamos a precargar Sección y Circuito si el distrito es Provincia
            # de Buenos Aires, para cualquier otro distrito no los vamos a precargar
            # ya que estos campos se ocultan al usuario y no va a poder editarlos.
            #
            # Si los precargamos corremos el riesgo de que si en la preidentificación
            # estaba mal la sección o el circuito obtendremos el error de que la mesa
            # no corresponde a dicha combinación y el usuario no podrá corregirlos
            # ya que los campos están ocultos.
            if pre_identificacion.distrito.numero == settings.DISTRITO_PBA:
                if pre_identificacion.seccion is not None:
                    initial['seccion'] = pre_identificacion.seccion.numero
                if pre_identificacion.circuito is not None:
                    initial['circuito'] = pre_identificacion.circuito.numero
        return initial

    def get(self, *args, **kwargs):
        logger.info('Inicio identificación', id=self.attachment.id)
        fiscal = self.request.user.fiscal
        attachment = self.attachment
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
            return redirect('siguiente-accion')

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
        logger.info('Error identificacion', id=self.attachment.id)
        return super().form_invalid(form)

    @transaction.atomic
    def form_valid(self, form):
        identificacion = form.save(commit=False)
        identificacion.status = Attachment.STATUS.identificada
        identificacion.fiscal = self.request.user.fiscal
        identificacion.attachment = self.attachment
        identificacion.save()
        self.attachment.desasignar_a_fiscal()  # Le bajamos la cuenta.
        messages.info(
            self.request,
            f'Mesa Nº {identificacion.mesa} - circuito {identificacion.mesa.circuito} identificada',
        )
        logger.info('Fin identificación', id=self.attachment.id)
        return super().form_valid(form)
