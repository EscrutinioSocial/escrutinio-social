from urllib import parse

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.text import get_text_list
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from djgeojson.views import GeoJSONLayerView
from django.contrib.auth.mixins import AccessMixin
from constance import config

from .models import (
    Distrito,
    Seccion,
    Circuito,
    Categoria,
    LugarVotacion,
    Mesa,
    ConfiguracionComputo,
    ConfiguracionComputoDistrito,
    OPCIONES_A_CONSIDERAR,
    TIPOS_DE_AGREGACIONES,
    NIVELES_AGREGACION,
    NIVELES_DE_AGREGACION,
)
from .resultados import Proyecciones, AvanceDeCarga, NIVEL_DE_AGREGACION, create_sumarizador

ESTRUCTURA = {None: Seccion, Seccion: Circuito, Circuito: LugarVotacion, LugarVotacion: Mesa, Mesa: None}


class StaffOnlyMixing:
    """
    Mixin para que sólo usuarios tipo "staff"
    accedan a la vista.
    """

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class VisualizadoresOnlyMixin(AccessMixin):
    """
    Mixin para que sólo usuarios visualizadores
    accedan a la vista.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.fiscal.esta_en_grupo('visualizadores'):
            return self.handle_no_permission()
        pk = kwargs.get('pk')
        categoria = get_object_or_404(Categoria, id=pk)

        if categoria.sensible and not request.user.fiscal.esta_en_grupo('visualizadores_sensible'):
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)


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


class ResultadosCategoriaBase(VisualizadoresOnlyMixin, TemplateView):
    """
    Clase base para subclasear vistas de resultados
    """

    template_name = "elecciones/resultados.html"

    def dispatch(self, *args, **kwargs):
        pk = self.kwargs.get('pk')
        if pk is None:
            return redirect('resultados-categoria', pk=Categoria.objects.first().id)
        return super().dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.sumarizador = self.create_sumarizador()
        self.ocultar_sensibles = not request.user.fiscal.esta_en_grupo('visualizadores_sensible')

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.sumarizador.filtros:
            context['para'] = get_text_list([
                objeto.nombre_completo() for objeto in self.sumarizador.filtros
            ], " y ")
        else:
            context['para'] = 'todo el país'

        pk = self.kwargs.get('pk')
        if pk is None:
            pk = Categoria.objects.first().id
        categoria = get_object_or_404(Categoria, id=pk)
        context['object'] = categoria
        context['categoria_id'] = categoria.id
        context['resultados'] = self.get_resultados(categoria)
        context['show_plot'] = settings.SHOW_PLOT

        # Agregamos al contexto el modo de elección; para cada partido decidimos
        # que porcentaje vamos a visualizar (porcentaje_positivos o
        # porcentaje_validos) dependiendo del tipo de elección.
        context['modo_eleccion']  = settings.MODO_ELECCION
        # Para no hardcodear las opciones en el html las agregamos al contexto.
        context['modo_paso']      = settings.ME_OPCION_PASO
        context['modo_generales'] = settings.ME_OPCION_GEN

        if settings.SHOW_PLOT:
            chart = self.get_plot_data(context['resultados'])
            context['plot_data'] = chart
            context['chart_values'] = [v['y'] for v in chart]
            context['chart_keys'] = [v['key'] for v in chart]
            context['chart_colors'] = [v['color'] for v in chart]

        # Las pestañas de categorías que se muestran son las que sean
        # comunes a todas las mesas filtradas.

        # Para el cálculo se filtran categorías activas que estén relacionadas
        # a las mesas.
        mesas = self.sumarizador.mesas(categoria)
        categorias = Categoria.para_mesas(mesas)
        if self.ocultar_sensibles:
            categorias = categorias.exclude(sensible=True)

        context['categorias'] = categorias.order_by('id')
        context['distritos'] = Distrito.objects.all().order_by('numero')
        return context

    def create_sumarizador(self):
        return create_sumarizador(
            parametros_sumarizacion=[
                self.get_tipo_de_agregacion(),
                self.get_opciones_a_considerar(),
                *self.get_filtro_por_nivel()
            ],
            tecnica_de_proyeccion=next(
                (tecnica for tecnica in Proyecciones.tecnicas_de_proyeccion()
                 if str(tecnica.id) == self.get_tecnica_de_proyeccion()), None)
        )

    def get_filtro_por_nivel(self):
        nivel_de_agregacion = None
        ids_a_considerar = None
        for nivel in reversed(NIVELES_AGREGACION):
            if nivel in self.request.GET:
                nivel_de_agregacion = nivel
                ids_a_considerar = self.request.GET.getlist(nivel)

        return (nivel_de_agregacion, ids_a_considerar)

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

    def get_plot_data(self, resultados):
        return [{
            'key': str(k),
            'y': v["votos"],
            'color': k.color if not isinstance(k, str) else '#CCCCCC'
        } for k, v in resultados.tabla_positivos().items()]


class ResultadosCategoria(ResultadosCategoriaBase):
    """
    Vista principal para el cálculo de resultados
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_de_agregaciones'] = TIPOS_DE_AGREGACIONES
        context['tipos_de_agregaciones_seleccionado'] = self.get_tipo_de_agregacion()
        context['opciones_a_considerar'] = OPCIONES_A_CONSIDERAR
        context['opciones_a_considerar_seleccionado'] = self.get_opciones_a_considerar()
        context['tecnicas_de_proyeccion'] = self.get_tecnicas_de_proyeccion()
        context['tecnicas_de_proyeccion_seleccionado'] = self.get_tecnica_de_proyeccion()
        return context


class MesasDeCircuito(ResultadosCategoria):

    template_name = "elecciones/mesas_circuito.html"

    def dispatch(self, *args, **kwargs):
        pk = self.kwargs.get('pk')
        if pk is None:
            pk = Categoria.objects.first().id
        mesa_id = self.request.GET.get('mesa')
        if mesa_id is None:
            circuito = get_object_or_404(Circuito, id=self.request.GET.get('circuito'))
            mesa_id = circuito.mesas.all().order_by("numero").first().id
            url_params = self.request.GET.copy()
            url_params['mesa'] = mesa_id
            query_string = parse.urlencode(url_params)
            url_base = reverse('mesas-circuito', args=[pk])
            # agregamos el mesa_id de la primer mesa al query string
            redirect_url = f"{url_base}?{query_string}"
            return redirect(redirect_url)
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categoria = context['object']
        circuito = get_object_or_404(Circuito, id=self.request.GET.get('circuito'))
        context['circuito_seleccionado'] = circuito
        mesas = circuito.mesas.all().order_by("numero")
        context['mesas'] = mesas
        mesa = Mesa.objects.get(id=self.request.GET.get('mesa'))
        context['resultados'] = self.sumarizador.votos_reportados(
            categoria,
            mesas.filter(id=mesa.id)
        )
        context['mesa_seleccionada'] = mesa
        context['mensaje_no_hay_info'] = f'No hay datos para la categoría {categoria} en la mesa {mesa}'
        context['url_params'] = self._evitar_duplicado_mesa_en_query_string(self.request.GET.copy())
        return context

    def _evitar_duplicado_mesa_en_query_string(self, url_params_original):
        if 'mesa' in url_params_original:
            del url_params_original['mesa']
        return parse.urlencode(url_params_original)


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

        return context


class ResultadosComputoCategoria(ResultadosCategoriaBase):

    template_name = "elecciones/resultados_computo.html"

    def dispatch(self, *args, **kwargs):
        pk = self.kwargs.get('pk')
        if pk is None:
            return redirect('resultados-computo', pk=Categoria.objects.first().id)
        return super().dispatch(*args, **kwargs)

    def create_sumarizador(self):
        """
        Crea un sumarizador basado en una configuración guardada en la base
        """
        nivel_de_agregacion, ids_a_considerar = self.get_filtro_por_nivel()
        fiscal = self.request.user.fiscal

        # Tenemos que considerar todo el país.
        if nivel_de_agregacion is None or ids_a_considerar is None or len(ids_a_considerar) > 1:
            # Configuracion por fiscal, ponele que usamos la primera que tenga.
            configuracion_combinada = ConfiguracionComputo.objects.filter(fiscal=fiscal).first()

            # Si no tiene ninguna, usamos la global.
            if configuracion_combinada is None:
                configuracion_combinada = ConfiguracionComputo.objects.first()

            self.configuracion_combinada = configuracion_combinada
            return create_sumarizador(configuracion_combinada=configuracion_combinada)
        else:
            self.configuracion_combinada = None

        # Recién ahora averiguamos cómo computar:
        entidad = NIVEL_DE_AGREGACION[nivel_de_agregacion].objects.get(id=ids_a_considerar[0])
        distrito = entidad if nivel_de_agregacion == NIVELES_DE_AGREGACION.distrito else entidad.distrito

        # Configuracion por fiscal, ponele que usamos la primera que tenga.
        # Si no tiene ninguna, usamos la global.
        configuracion_distrito = ConfiguracionComputoDistrito.objects.filter(
                configuracion__fiscal=fiscal,
                distrito=distrito
        ).first()

        if configuracion_distrito is None:
            configuracion_distrito = ConfiguracionComputoDistrito.objects.filter(
                configuracion__nombre=config.CONFIGURACION_COMPUTO_PUBLICA,
                distrito=distrito
            ).first()

        self.agregacion = configuracion_distrito.agregacion
        self.opciones = configuracion_distrito.opciones
        self.tecnica_de_proyeccion = configuracion_distrito.proyeccion

        return create_sumarizador(
            parametros_sumarizacion=[
                nivel_de_agregacion,
                ids_a_considerar,
            ],
            configuracion_distrito=configuracion_distrito,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if (self.configuracion_combinada):
            context['configuracion_computo'] = self.configuracion_combinada.nombre
        else:
            context['tipo_de_agregacion'] = TIPOS_DE_AGREGACIONES[self.agregacion]
            context['opciones'] = OPCIONES_A_CONSIDERAR[self.opciones]
            context['tecnica_de_proyeccion'] = self.tecnica_de_proyeccion

        if self.sumarizador.filtros:
            context['para'] = get_text_list([
                objeto.nombre_completo() for objeto in self.sumarizador.filtros
            ], " y ")
        else:
            context['para'] = 'todo el país'

        pk = self.kwargs.get('pk')
        if pk is None:
            pk = Categoria.objects.first().id
        categoria = get_object_or_404(Categoria, id=pk)
        context['object'] = categoria
        context['categoria_id'] = categoria.id
        context['resultados'] = self.get_resultados(categoria)
        context['show_plot'] = settings.SHOW_PLOT

        # Agregamos al contexto el modo de elección; para cada partido decidimos
        # que porcentaje vamos a visualizar (porcentaje_positivos o
        # porcentaje_sin_nulos) dependiendo del tipo de elección.
        context['modo_eleccion']  = settings.MODO_ELECCION
        # Para no hardcodear las opciones en el html las agregamos al contexto.
        context['modo_paso']      = settings.ME_OPCION_PASO
        context['modo_generales'] = settings.ME_OPCION_GEN

        if settings.SHOW_PLOT:
            chart = self.get_plot_data(context['resultados'])
            context['plot_data'] = chart
            context['chart_values'] = [v['y'] for v in chart]
            context['chart_keys'] = [v['key'] for v in chart]
            context['chart_colors'] = [v['color'] for v in chart]

        # Las pestañas de categorías que se muestran son las que sean
        # comunes a todas las mesas filtradas.

        # Para el cálculo se filtran categorías activas que estén relacionadas
        # a las mesas.
        mesas = self.sumarizador.mesas(categoria)
        categorias = Categoria.para_mesas(mesas)
        if self.ocultar_sensibles:
            categorias = categorias.exclude(sensible=True)

        context['categorias'] = categorias.order_by('id')
        context['distritos'] = Distrito.objects.all().order_by('numero')
        context['computo'] = True
        return context

    def get_tipo_de_agregacion(self):
        return self.agregacion

    def get_opciones_a_considerar(self):
        return self.opciones

    def get_tecnica_de_proyeccion(self):
        return self.tecnica_de_proyeccion
