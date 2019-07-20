from django.views.generic.edit import CreateView
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Problema
from elecciones.views import StaffOnlyMixing
from elecciones.models import Mesa


class ProblemaCreate(StaffOnlyMixing, CreateView):
    model = Problema
    template_name = "problemas/problema.html"
    fields = ['problema', 'descripcion']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mesa'] = get_object_or_404(Mesa, numero=self.kwargs['mesa_numero'])
        return context

    def form_valid(self, form):

        context = self.get_context_data()
        problema = form.save(commit=False)
        problema.reportado_por = self.request.user.fiscal

        problema.mesa = context['mesa']
        problema.save()
        messages.success(self.request, 'El problema fue reportado. Gracias.')
        return redirect('siguiente-accion')

class ProblemaResolve(StaffOnlyMixing, CreateView):
    http_method_names = ['post']
    identificacion_creada = None

    def form_valid(self, form):
        fiscal = self.request.user.fiscal
        identificacion = form.save(commit=False)
        identificacion.attachment = self.attachment
        identificacion.fiscal = fiscal
        identificacion.status = Identificacion.STATUS.problema
        identificacion.save()

        # XXX TOdo mal.

        # Creo el problema asociado.
        tipo_de_problema = ReporteDeProblema.TIPOS_DE_PROBLEMA.spam # XXX Seleccionar el apropiado.
        descripcion = None # Tomar input del usuario.
        Problema.reportar_problema(fiscal, descripcion, tipo_de_problema, identificacion=identificacion)

        self.identificacion_creada = identificacion
        messages.info(
            self.request,
            f'Guardado como "{identificacion.get_status_display()}"',
        )
        return redirect(self.get_success_url())

