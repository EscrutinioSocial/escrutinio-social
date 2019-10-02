from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import get_text_list
from django.views.generic.base import TemplateView

from .definiciones import *

from elecciones.models import (
    Distrito,
    Seccion,
    Circuito,
    Categoria,
    LugarVotacion,
    Mesa,
    OPCIONES_A_CONSIDERAR,
    TIPOS_DE_AGREGACIONES,
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
