from django.shortcuts import redirect
from django.urls import reverse
from django.db import transaction

import structlog

from adjuntos.consolidacion import consolidar_identificaciones
from adjuntos.models import Identificacion
from .identificacion_create import IdentificacionCreateView

logger = structlog.get_logger(__name__)


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
        identificacion.attachment.desasignar_a_fiscal()
        # Como viene desde una UB, consolidamos el attachment y ya le pasamos la mesa
        consolidar_identificaciones(identificacion.attachment)
        return redirect(self.get_success_url())
