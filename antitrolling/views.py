from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.views.generic.base import TemplateView

from constance import config
from fiscales.models import Fiscal


NO_PERMISSION_REDIRECT = 'permission-denied'

@login_required
@user_passes_test(lambda u: u.fiscal.esta_en_grupo('supervisores'), login_url=NO_PERMISSION_REDIRECT)
def cambiar_status_troll(request, fiscal_id, prender):
    fiscal = get_object_or_404(Fiscal, id=fiscal_id)

    # el parámetro prender llega como un String, "True" o "False"
    prender_bool = prender == "True"

    if prender_bool:
        fiscal.marcar_como_troll(request.user.fiscal)
    else:
        fiscal.quitar_marca_troll(request.user.fiscal, 0)  # XXX Pendiente el nuevo score.

    messages.info(
        request,
        f'Validador {fiscal} modificado.',
    )
    return redirect('admin:fiscales_fiscal_changelist')


class MonitorAntitrolling(TemplateView):
    """
    Vista principal monitor antitrolling.
    """

    template_name = "antitrolling/monitoreo_antitrolling.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fiscales'] = Fiscal.objects.count()
        context['umbral_troll'] = config.SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL
        return context
