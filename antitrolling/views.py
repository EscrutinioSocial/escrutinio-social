import math

from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.views.generic.base import TemplateView

from constance import config
from elecciones.models import Carga
from adjuntos.models import Identificacion
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
        # umbral troll
        context['umbral_troll'] = ParametrosAntitrolling.umbral_troll
        # data fiscales
        context['fiscales'] = ParametrosAntitrolling.cantidad_fiscales
        data_troll = FiscalesTroll().set_umbrales_de_peligro(3, 5, 7)
        context['fiscales_troll'] = data_troll.info_para_renderizar()
        context['fiscales_no_troll'] = FiscalesNoTroll(data_troll).info_para_renderizar()
        rangos_scoring = [
            FiscalesEnRangoScoringTroll().setRangoPorcentajes(80, None).set_umbrales_de_peligro(5, 7, 10),
            FiscalesEnRangoScoringTroll().setRangoPorcentajes(60, 80).set_umbrales_de_peligro(10, 15, 20),
            FiscalesEnRangoScoringTroll().setRangoPorcentajes(30, 60).set_umbrales_de_peligro(30, 40, 50),
            FiscalesEnRangoScoringTroll().setRangoPorcentajes(0, 30),
            FiscalesEnRangoScoringTroll().setRangoPorcentajes(None, 0),
        ]
        context['rangos_scoring'] = [rango.info_para_renderizar() for rango in rangos_scoring]
        # data acciones
        context['identificaciones'] = GeneradorInfoAcciones(Identificacion.objects.filter(procesada=True)).rangos()
        context['cargas'] = GeneradorInfoAcciones(Carga.objects.filter(procesada=True)).rangos()
        return context


class ParametrosAntitrolling():
    umbral_troll = None
    cantidad_fiscales = None

    @classmethod
    def reset(cls):
        cls.umbral_troll = config.SCORING_MINIMO_PARA_CONSIDERAR_QUE_FISCAL_ES_TROLL
        cls.cantidad_fiscales = Fiscal.objects.filter(ingreso_alguna_vez=True).count()


class FiscalesEnRangoScoringTroll():
    def __init__(self):
        self.indicador_de_peligro = NoHayPeligro()
        self.cantidad = None

    def setRangoPorcentajes(self, desde_porcentaje, hasta_porcentaje):
        self.desde_scoring = None if desde_porcentaje == None else math.floor(
            ((ParametrosAntitrolling.umbral_troll * desde_porcentaje) / 100) + 1)
        self.desde_porcentaje = desde_porcentaje
        self.hasta_scoring = None if hasta_porcentaje == None else math.floor(
            (ParametrosAntitrolling.umbral_troll * hasta_porcentaje) / 100)
        self.hasta_porcentaje = hasta_porcentaje
        self.cantidad = None
        return self

    def set_umbrales_de_peligro(self, amarillo, naranja, rojo):
        self.indicador_de_peligro = IndicadorDePeligro().set_umbrales(amarillo, naranja, rojo)
        return self

    def cantidad_fiscales(self):
        self.calcular()
        return self.cantidad

    def porcentaje_fiscales(self):
        self.calcular()
        return (self.cantidad * 100) / ParametrosAntitrolling.cantidad_fiscales

    def texto_porcentaje(self):
        if self.desde_porcentaje != None and self.hasta_porcentaje != None:
            if self.desde_porcentaje == 0:
                return f"Hasta el {self.hasta_porcentaje} %  del mínimo"
            else:
                return f"{self.desde_porcentaje} % - {self.hasta_porcentaje} % del mínimo"
        elif (self.desde_porcentaje != None and self.hasta_porcentaje == None):
            return f"Más del {self.desde_porcentaje} % del mínimo"
        elif (self.desde_porcentaje == None and self.hasta_porcentaje != None):
            if (self.hasta_porcentaje == 0):
                return f"Scoring negativo o cero"
            else:
                return "Hasta el {self.hasta_porcentaje} %"
        else:
            return "Total"

    def texto_rango(self):
        if self.desde_scoring != None and self.hasta_scoring != None:
            return f"{self.desde_scoring} a {self.hasta_scoring} puntos"
        elif self.desde_scoring != None and self.hasta_scoring == None:
            return f"{self.desde_scoring} puntos o más"
        elif self.desde_scoring == None and self.hasta_scoring != None:
            return f"{self.hasta_scoring} puntos o menos"
        else:
            return "sin límites"

    def indicador_peligro(self):
        return self.indicador_de_peligro.indicador_peligro(self.porcentaje_fiscales())

    def info_para_renderizar(self):
        return RangoScoringParaRenderizar(self)

    def calcular(self):
        if (self.cantidad == None):
            query = self.build_query()
            self.cantidad = query.count()

    def build_query(self):
        query = Fiscal.objects.filter(ingreso_alguna_vez=True).filter(troll=False)
        if (self.desde_scoring != None):
            query = query.filter(puntaje_scoring_troll__gte=self.desde_scoring)
        if (self.hasta_scoring != None):
            query = query.filter(puntaje_scoring_troll__lte=self.hasta_scoring)
        return query


class FiscalesTroll(FiscalesEnRangoScoringTroll):
    def __init__(self):
        super().__init__()

    def build_query(self):
        return Fiscal.objects.filter(ingreso_alguna_vez=True).filter(troll=True)

    def texto_porcentaje(self):
        return "Considerados troll"

    def texto_rango(self):
        return ""


class FiscalesNoTroll(FiscalesEnRangoScoringTroll):
    def __init__(self, data_troll):
        super().__init__()
        self.data_troll = data_troll
        self.cantidad = ParametrosAntitrolling.cantidad_fiscales - data_troll.cantidad_fiscales()

    def build_query(self):
        raise Exception("Should not build query for a FiscalesNoTroll instance")

    def texto_porcentaje(self):
        return "No considerados troll"

    def texto_rango(self):
        return ""


class GeneradorInfoAcciones():
    def __init__(self, query_inicial):
        super().__init__()
        self.query_inicial = query_inicial
        self._rangos = None

    def calcular(self):
        if not self._rangos:
            cantidad_total_acciones = self.query_inicial.count()
            cantidad_validas = self.query_inicial.filter(invalidada=False).count()
            cantidad_invalidadas = cantidad_total_acciones - cantidad_validas
            self._rangos = [
                RangoAccionesParaRenderizar('Total', cantidad_total_acciones, cantidad_total_acciones),
                RangoAccionesParaRenderizar('Válidas', cantidad_validas, cantidad_total_acciones),
                RangoAccionesParaRenderizar('Invalidadas', cantidad_invalidadas, cantidad_total_acciones).set_umbrales_de_peligro(4,7,10)
            ]

    def rangos(self):
        self.calcular()
        return self._rangos


class RangoScoringParaRenderizar():
    def __init__(self, info_fiscales_en_rango):
        self.info_fiscales = info_fiscales_en_rango
        self.texto_porcentaje = info_fiscales_en_rango.texto_porcentaje()
        self.texto_rango = info_fiscales_en_rango.texto_rango()
        self.cantidad = info_fiscales_en_rango.cantidad_fiscales()
        self.porcentaje = round(info_fiscales_en_rango.porcentaje_fiscales(), 2)
        self.indicador_peligro = info_fiscales_en_rango.indicador_peligro()


class RangoAccionesParaRenderizar():
    def __init__(self, texto, cantidad, cantidad_total):
        self.texto = texto
        self.cantidad = cantidad
        porcentaje_calculado = 100 if cantidad == cantidad_total else (cantidad * 100) / cantidad_total
        self.porcentaje = round(porcentaje_calculado, 2)
        self.calcular_indicador_peligro(NoHayPeligro())

    def set_umbrales_de_peligro(self, amarillo, naranja, rojo):
        self.calcular_indicador_peligro(IndicadorDePeligro().set_umbrales(amarillo, naranja, rojo))
        return self

    def calcular_indicador_peligro(self, criterio_peligro):
        self.indicador_peligro = criterio_peligro.indicador_peligro(self.porcentaje)


class IndicadorDePeligro():
    indicador_rojo = "rojo"
    indicador_naranja = "naranja"
    indicador_amarillo = "amarillo"
    indicador_verde = "verde"

    def set_umbrales(self, umbral_amarillo, umbral_naranja, umbral_rojo):
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


class NoHayPeligro():
    def indicador_peligro(self, valor):
        return IndicadorDePeligro.indicador_verde


@login_required
def limpiar_marcas_troll(request):
    print('en limpiar_marcas_troll')
    request_data = request.POST.copy()
    try: 
        hasta_scoring = int(request.POST.copy().get('hasta_puntaje'))
        nuevo_scoring = int(request.POST.copy().get('nuevo_puntaje'))
        if (hasta_scoring >= 0):
            Fiscal.destrolleo_masivo(request.user.fiscal, hasta_scoring, nuevo_scoring)
            messages.info(
                request, 
                f'Quitada la marca troll para fiscales con scoring hasta {hasta_scoring} - arrancan con scoring {nuevo_scoring}')
        else:
            messages.info(request, 'El límite de puntaje para quitar la marca troll debe ser positivo')
    except ValueError:
        messages.info(request, 'Debe ingresar valores numéricos')
    return redirect("monitoreo-antitrolling")


