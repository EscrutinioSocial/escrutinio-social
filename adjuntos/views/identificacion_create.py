from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic.edit import CreateView
from django.core.serializers import serialize
from django.conf import settings
from django.db import transaction
from constance import config
from sentry_sdk import capture_message
import structlog

from adjuntos.forms import IdentificacionForm
from adjuntos.models import Attachment, Identificacion
from adjuntos.consolidacion import consolidar_identificaciones
from fiscales.acciones import redirect_siguiente_accion
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
        modo_ub = self.request.GET.get('modo_ub', False)

        return redirect_siguiente_accion(modo_ub)

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
            logger.warning(
                'Identificación no autorizada', attachment_id=attachment.id,
                tenia_attachment=fiscal.attachment_asignado.id if fiscal.attachment_asignado else None
            )
            # Lo mandamos nuevamente a que se le dé algo para hacer.
            return redirect('siguiente-accion')

        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(IdentificacionCreateView, self).get_context_data(**kwargs)
        context['attachment'] = self.attachment
        context['recibir_problema'] = 'asignar-problema'
        context['dato_id'] = self.attachment.id
        context['form_problema'] = IdentificacionDeProblemaForm()
        context['url_video_instructivo'] = config.URL_VIDEO_INSTRUCTIVO
        return context

    def form_invalid(self, form):
        logger.info('Error identificación', id=self.attachment.id)
        return super().form_invalid(form)

    @transaction.atomic
    def form_valid(self, form):
        modo_ub = self.request.GET.get('modo_ub', False)
        identificacion = form.save(commit=False)
        identificacion.status = Attachment.STATUS.identificada
        identificacion.fiscal = self.request.user.fiscal
        identificacion.attachment = self.attachment

        if modo_ub:
            identificacion.source = Identificacion.SOURCES.csv

        identificacion.save()
        self.attachment.desasignar_a_fiscal()  # Le bajamos la cuenta.

        if modo_ub:
            # Como viene desde una UB consolidamos el attachment.
            consolidar_identificaciones(identificacion.attachment)

        messages.info(
            self.request,
            f'Mesa Nº {identificacion.mesa} - circuito {identificacion.mesa.circuito} identificada',
        )
        logger.info('Fin identificación', id=self.attachment.id)
        return super().form_valid(form)
