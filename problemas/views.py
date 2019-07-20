from django.views.generic.edit import CreateView
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Problema
from elecciones.views import StaffOnlyMixing
from elecciones.models import Mesa
from django.contrib.auth.decorators import user_passes_test, login_required

NO_PERMISSION_REDIRECT = 'permission-denied'

@login_required
@user_passes_test(lambda u: u.fiscal.esta_en_grupo('validadores'), login_url=NO_PERMISSION_REDIRECT)
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

@login_required
@user_passes_test(lambda u: u.fiscal.esta_en_grupo('supervisores'), login_url=NO_PERMISSION_REDIRECT)
def cambiar_estado_problema(request, problema_id, nuevo_estado):
    problema = get_object_or_404(Problema, id=problema_id)

    if nuevo_estado == Problema.ESTADOS.en_curso:
        problema.aceptar()
    elif nuevo_estado == Problema.ESTADOS.resuelto:
        problema.resolver(request.user)
    elif nuevo_estado == Problema.ESTADOS.descartado:
        problema.descartar(request.user)

    mensaje = {
        Problema.ESTADOS.en_curso: 'confirmado',
        Problema.ESTADOS.resuelto: 'resuelto',
        Problema.ESTADOS.descartado: 'descartado'
    }

    messages.info(
        request,
        f'Problema {problema.id} {mensaje[nuevo_estado]}.',
    )
    return redirect('admin:problemas_problema_changelist')
