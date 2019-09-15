import math

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
        ParametrosAntitrolling.reset()
        context = super().get_context_data(**kwargs)
        context['umbral_troll'] = ParametrosAntitrolling.umbral_troll
        context['fiscales'] = ParametrosAntitrolling.cantidad_fiscales
        return context


class ParametrosAntitrolling():
    umbral_troll = None
    cantidad_fiscales = None

    @classmethod
    def reset(cls):
        cls.umbral_troll = config.SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL
        cls.cantidad_fiscales = Fiscal.objects.count()


class FraccionFiscalesPorScoringTroll():
    def setRangoPorcentajes(self, desde_porcentaje, hasta_porcentaje):
        self.desde_scoring = None if desde_porcentaje == None else floor(
            ((ParametrosAntitrolling.umbral_troll * desde_porcentaje) / 100) + 1)
        self.desde_porcentaje = desde_porcentaje
        self.hasta_scoring = None if hasta_porcentaje == None else floor(
            (ParametrosAntitrolling.umbral_troll * hasta_porcentaje) / 100)
        self.hasta_porcentaje = desde_porcentaje
        self.cantidad = None
        return self

    def set_indicador_de_peligro(self, indicador):
        self.indicador_de_peligro = indicador
        return self

    def cantidad_fiscales(self):
        self.calcular()
        return self.cantidad

    def porcentaje_fiscales(self):
        self.calcular()
        return (self.cantidad * 100) / ParametrosAntitrolling.umbral_troll

    def indicador_peligro(self):
        return self.indicador_de_peligro.indicador_peligro(self.porcentaje_fiscales())
        
    def calcular(self):
        if (self.cantidad == None):
            query = Fiscales.objects.filter(troll=False)
            if (self.desde_scoring != None):
                query = query.filter(puntaje_scoring_troll >= self.desde_scoring)
            if (self.hasta_scoring != None):
                query = query.filter(puntaje_scoring_troll <= self.hasta_scoring)
            self.cantidad = query.count()


class IndicadorDePeligro():
    indicador_rojo = "rojo"
    indicador_naranja = "naranja"
    indicador_amarillo = "amarillo"
    indicador_verde = "verde"

    def set_umbrales(self, umbral_rojo, umbral_naranja, umbral_amarillo):
        self.umbral_rojo = umbral_rojo
        self.umbral_naranja = umbral_naranja
        self.umbral_amarillo = umbral_amarillo
        return self

    def indicador_peligro(self, valor):
        if (valor >= self.umbral_rojo):
            return self.indicador_rojo
        elif (valor >= self.umbral_naranja):
            return self.indicador_naranja
        elif (valor >= self.umbral_amarillo):
            return self.indicador_amarillo
        else:
            return self.indicador_verde


