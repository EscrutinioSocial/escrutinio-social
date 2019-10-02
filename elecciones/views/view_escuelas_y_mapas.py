from django.conf import settings
from django.urls import reverse
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from djgeojson.views import GeoJSONLayerView

from .definiciones import *

from elecciones.models import (
    LugarVotacion,
)


class LugaresVotacionGeoJSON(GeoJSONLayerView):
    """
    Devuelve el archivo geojson con la información geoposicional
    de las escuelas, que es consumido por la el template de la
    vista :class:`Mapa`

    cada point tiene un color que determina si hay o no alguna mesa computada
    en esa escuela, ver  :attr:`elecciones.LugarVotacion.color`

    Documentación de referencia:

        https://django-geojson.readthedocs.io/
    """

    model = LugarVotacion
    properties = ('id', 'color')  # 'popup_html',)

    def get_queryset(self):
        qs = super().get_queryset()
        ids = self.request.GET.get('ids')
        if ids:
            qs = qs.filter(id__in=ids.split(','))
        elif 'todas' in self.request.GET:
            return qs
        elif 'testigo' in self.request.GET:
            qs = qs.filter(mesas__es_testigo=True).distinct()

        return qs


class EscuelaDetailView(StaffOnlyMixing, DetailView):
    """
    Devuelve una tabla estática con información general de una esuela
    que se muestra an un popup al hacer click sobre una escuela en :class:`Mapa`
    """
    template_name = "elecciones/detalle_escuela.html"
    model = LugarVotacion

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mostrar_electores'] = not settings.OCULTAR_CANTIDADES_DE_ELECTORES
        return context


class Mapa(StaffOnlyMixing, TemplateView):
    """
    Vista estática que carga el mapa que consume el geojson de escuelas
    el template utiliza leaflet

    https://django-leaflet.readthedocs.io/en/latest/

    """

    template_name = "elecciones/mapa.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        geojson_url = reverse("geojson")
        if 'ids' in self.request.GET:
            query = self.request.GET.urlencode()
            geojson_url += f'?{query}'
        elif 'testigo' in self.request.GET:
            query = 'testigo=si'
            geojson_url += f'?{query}'

        context['geojson_url'] = geojson_url
        return context
