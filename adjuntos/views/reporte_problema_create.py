from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.utils.functional import cached_property
from django.views.generic.edit import CreateView, FormView
from django.core.serializers import serialize

import structlog

from adjuntos.models import Attachment, Identificacion
from problemas.models import Problema
from problemas.forms import IdentificacionDeProblemaForm

logger = structlog.get_logger(__name__)

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
