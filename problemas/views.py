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
        messages.success(self.request, 'El problema de esta carga fue reportado. Gracias')

        return redirect('post-reportar-problema', mesa=context['mesa'].numero)
