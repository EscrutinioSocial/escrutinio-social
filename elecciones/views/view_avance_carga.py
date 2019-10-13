from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import get_text_list
from django.views.generic.base import TemplateView

from .definiciones import VisualizadoresOnlyMixin

from elecciones.models import (
    Distrito,
    Seccion,
    Circuito,
    Categoria,
    LugarVotacion,
    Mesa,
    MesaCategoria,
    OPCIONES_A_CONSIDERAR,
    TIPOS_DE_AGREGACIONES,
    NIVELES_AGREGACION,
)
from elecciones.proyecciones import Proyecciones
from elecciones.avance_carga import AvanceDeCarga

from elecciones.resultados_resumen import (
    GeneradorDatosFotosConsolidado, GeneradorDatosPreidentificacionesConsolidado,
    GeneradorDatosCargaParcialConsolidado, GeneradorDatosCargaTotalConsolidado
)


ESTRUCTURA = {None: Seccion, Seccion: Circuito, Circuito: LugarVotacion, LugarVotacion: Mesa, Mesa: None}


class AvanceDeCargaCategoria(VisualizadoresOnlyMixin, TemplateView):
    """
    Vista principal avance de carga de actas.
    """

    template_name = "elecciones/avance_carga.html"

    def dispatch(self, *args, **kwargs):
        pk = self.kwargs.get('pk')
        if pk is None:
            return redirect('avance-carga', pk=Categoria.objects.first().id)
        return super().dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        nivel_de_agregacion = None
        ids_a_considerar = None
        for nivel in reversed(NIVELES_AGREGACION):
            if nivel in self.request.GET:
                nivel_de_agregacion = nivel
                ids_a_considerar = self.request.GET.getlist(nivel)

        self.sumarizador = AvanceDeCarga(nivel_de_agregacion, ids_a_considerar)
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        return [self.kwargs.get("template_name", self.template_name)]

    def get_resultados(self, categoria):
        return self.sumarizador.get_resultados(categoria)

    def get_tipo_de_agregacion(self):
        # TODO el default también está en Sumarizador.__init__
        return self.request.GET.get('tipoDeAgregacion', TIPOS_DE_AGREGACIONES.todas_las_cargas)

    def get_opciones_a_considerar(self):
        # TODO el default también está en Sumarizador.__init__
        return self.request.GET.get('opcionaConsiderar', OPCIONES_A_CONSIDERAR.todas)

    def get_tecnica_de_proyeccion(self):
        return self.request.GET.get('tecnicaDeProyeccion', settings.SIN_PROYECCION[0])

    def get_tecnicas_de_proyeccion(self):
        return [settings.SIN_PROYECCION] + [(str(tecnica.id), tecnica.nombre)
                                            for tecnica in Proyecciones.tecnicas_de_proyeccion()]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.sumarizador.filtros:
            context['para'] = get_text_list([objeto.nombre_completo() for objeto in self.sumarizador.filtros], " y ")
        else:
            context['para'] = 'todo el país'

        pk = self.kwargs.get('pk')

        categoria = get_object_or_404(Categoria, id=pk)
        context['object'] = categoria
        context['categoria_id'] = categoria.id
        context['resultados'] = self.get_resultados(categoria)

        # Para el cálculo se filtran categorías activas que estén relacionadas
        # a las mesas.
        mesas = self.sumarizador.mesas(categoria)
        context['categorias'] = Categoria.para_mesas(mesas).order_by('id')
        context['distritos'] = Distrito.objects.all().order_by('nombre')
        context['mostrar_electores'] = not settings.OCULTAR_CANTIDADES_DE_ELECTORES
        return context


class AvanceDeCargaResumen(TemplateView):
    """
    Vista principal avance de carga resumen
    """

    template_name = "elecciones/avance_carga_resumen.html"

    def dispatch(self, *args, **kwargs):
        self.base_carga_parcial = self.kwargs.get('carga_parcial')
        self.base_carga_total = self.kwargs.get('carga_total')
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # data fotos
        generador_datos_fotos = GeneradorDatosFotosConsolidado()
        generador_datos_carga_parcial = GeneradorDatosCargaParcialConsolidado()
        if self.base_carga_parcial == "solo_con_fotos":
            generador_datos_carga_parcial.set_query_base(MesaCategoria.objects.exclude(mesa__attachments=None))
        generador_datos_carga_total = GeneradorDatosCargaTotalConsolidado()
        if self.base_carga_total == "solo_con_fotos":
            generador_datos_carga_total.set_query_base(MesaCategoria.objects.exclude(mesa__attachments=None))
        context['base_carga_parcial'] = self.base_carga_parcial
        context['base_carga_total'] = self.base_carga_total
        context['data_fotos_nacion_pba'] = generador_datos_fotos.datos_nacion_pba()
        context['data_fotos_solo_nacion'] = generador_datos_fotos.datos_solo_nacion()
        context['data_preidentificaciones'] = GeneradorDatosPreidentificacionesConsolidado().datos()
        context['data_carga_parcial'] = generador_datos_carga_parcial.datos()
        context['data_carga_total'] = generador_datos_carga_total.datos()
        return context
