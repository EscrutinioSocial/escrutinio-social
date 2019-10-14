from urllib import parse
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import get_text_list
from django.views.generic.base import TemplateView
from django.contrib.auth.decorators import login_required, user_passes_test
from constance import config

from .definiciones import *

import django_excel as excel
from elecciones.busquedas import BusquedaDistritoOSeccion

from .models import (
    MesaCategoria,
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
from .resultados_resumen import (
    GeneradorDatosFotosConsolidado, GeneradorDatosPreidentificacionesConsolidado,
    GeneradorDatosCargaParcialConsolidado, GeneradorDatosCargaTotalConsolidado,
    SinRestriccion, RestriccionPorDistrito, RestriccionPorSeccion
)

from elecciones.proyecciones import Proyecciones, create_sumarizador
from elecciones.sumarizador import NIVEL_DE_AGREGACION


@login_required
@user_passes_test(lambda u: u.fiscal.esta_en_grupo('visualizadores'), login_url='permission-denied')
def menu_lateral_resultados(request, categoria_id):

    # Si no viene categoría mandamos a PV.
    categoria = categoria_id
    if categoria_id is None:
        categoria = Categoria.objects.get(slug=settings.SLUG_CATEGORIA_PRESI_Y_VICE).id
        return redirect('resultados-nuevo-menu', categoria_id=categoria)

    context = {}
    context['distritos'] = Distrito.objects.all().extra(
        select={'numero_int': 'CAST(numero AS INTEGER)'}
    ).prefetch_related(
        'secciones_politicas',
        'secciones',
        'secciones__circuitos'
    ).order_by('numero_int')
    context['cat_id'] = categoria
    return render(request, 'elecciones/menu-lateral-resultados.html', context=context)


class ResultadosCategoriaBase(VisualizadoresOnlyMixin, TemplateView):
    """
    Clase base para subclasear vistas de resultados
    """

    template_name = "elecciones/resultados.html"

    def dispatch(self, *args, **kwargs):
        pk = self.kwargs.get('pk')
        if pk is None:
            categoria_presi_y_vice = Categoria.objects.get(slug=settings.SLUG_CATEGORIA_PRESI_Y_VICE)
            return redirect('resultados-categoria', pk=categoria_presi_y_vice.id)
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
        categoria = get_object_or_404(Categoria, id=pk)
        context['object'] = categoria
        context['categoria_id'] = categoria.id
        resultados = self.get_resultados(categoria)
        context['resultados'] = resultados
        context['show_plot'] = settings.SHOW_PLOT

        # Agregamos al contexto el modo de elección; para cada partido decidimos
        # qué porcentaje vamos a visualizar (porcentaje_positivos o
        # porcentaje_validos) dependiendo del tipo de elección.
        context['modo_eleccion'] = settings.MODO_ELECCION
        # Para no hardcodear las opciones en el html las agregamos al contexto.
        context['modo_paso'] = settings.ME_OPCION_PASO
        context['modo_generales'] = settings.ME_OPCION_GEN

        context['mostrar_electores'] = not settings.OCULTAR_CANTIDADES_DE_ELECTORES

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
        categorias = self.sumarizador.categorias()
        if self.ocultar_sensibles:
            categorias = categorias.exclude(sensible=True)

        context['categorias'] = categorias.order_by('id')
        context['distritos'] = Distrito.objects.all().prefetch_related(
            'secciones_politicas',
            'secciones',
            'secciones__circuitos'
        ).order_by('numero')
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


class ResultadosCategoriaCuerpoCentral(ResultadosCategoria):
    template_name = "elecciones/resultados-cuerpo-central.html"


class ResultadosExport(ResultadosCategoria):

    def get_context_data(self, **kwargs):
        pk = self.kwargs.get('pk')
        categoria = get_object_or_404(Categoria, id=pk)
        self.filetype = self.kwargs.get('filetype')
        mesas = self.sumarizador.mesas(categoria)
        votos = self.sumarizador.votos_reportados(categoria, mesas)
        return {'votos': votos}

    def render_to_response(self, context, **response_kwargs):
        votos = context['votos']

        headers = ['seccion', 'numero seccion', 'circuito', 'codigo circuito', 'centro de votacion', 'mesa',
                   'opcion', 'votos']
        csv_list = [headers]

        for voto_mesa in votos:
            mesa = voto_mesa.carga.mesa
            opcion = voto_mesa.opcion.codigo
            votos = voto_mesa.votos
            fila = [mesa.lugar_votacion.circuito.seccion.nombre,
                    mesa.lugar_votacion.circuito.seccion.numero,
                    mesa.lugar_votacion.circuito.nombre,
                    mesa.lugar_votacion.circuito.numero,
                    mesa.lugar_votacion.nombre,
                    mesa.numero,
                    opcion,
                    votos]
            csv_list.append(fila)
        return excel.make_response(excel.pe.Sheet(csv_list), self.filetype)


class ResultadosComputoCategoria(ResultadosCategoriaBase):

    template_name = "elecciones/resultados_computo.html"

    def dispatch(self, *args, **kwargs):
        pk = self.kwargs.get('pk')
        if pk is None:
            return redirect('resultados-en-base-a-configuración', pk=Categoria.objects.first().id)
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
        context['en_base_a_configuracion'] = True

        if (self.configuracion_combinada):
            context['configuracion_computo'] = self.configuracion_combinada.nombre
        else:
            context['tipo_de_agregacion'] = TIPOS_DE_AGREGACIONES[self.agregacion]
            context['opciones'] = OPCIONES_A_CONSIDERAR[self.opciones]
            context['tecnica_de_proyeccion'] = self.tecnica_de_proyeccion

        return context

    def get_tipo_de_agregacion(self):
        return self.agregacion

    def get_opciones_a_considerar(self):
        return self.opciones

    def get_tecnica_de_proyeccion(self):
        return self.tecnica_de_proyeccion


class AvanceDeCargaResumen(TemplateView):
    """
    Vista principal avance de carga resumen
    """

    template_name = "elecciones/avance_carga_resumen.html"

    def dispatch(self, *args, **kwargs):
        self.base_carga_parcial = self.kwargs.get('carga_parcial')
        self.base_carga_total = self.kwargs.get('carga_total')
        self.restriccion_geografica_spec = self.kwargs.get('restriccion_geografica')
        self.restriccion_geografica = self.calcular_restriccion()
        self.categoria_spec = self.kwargs.get('categoria')
        if self.categoria_spec == 'None':
            self.categoria = Categoria.objects.filter(slug=settings.SLUG_CATEGORIA_PRESI_Y_VICE).first()
        else:
            self.categoria = Categoria.objects.filter(id=self.categoria_spec).first()
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # restricción geográfica
        context['nombre_restriccion_geografica'] = self.restriccion_geografica.nombre()
        context['hay_restriccion_geografica'] = self.restriccion_geografica.restringe_algo()
        context['slug_restriccion_geografica'] = self.restriccion_geografica.slug()
        context['ancho_dato'] = 's1' if self.restriccion_geografica.restringe_algo() else 's2'
        context['ancho_titulo'] = 's2' if self.restriccion_geografica.restringe_algo() else 's4'
        # categorias
        context['categorias'], context['hay_demasiadas_categorias'] = self.data_categorias_posibles()
        context['categoria_elegida'] = self.categoria_spec
        context['nombre_categoria_elegida'] = self.categoria.nombre
        # data fotos
        generador_datos_fotos = GeneradorDatosFotosConsolidado(self.restriccion_geografica)
        context['data_fotos_nacion_pba_restriccion'] = generador_datos_fotos.datos_nacion_pba_restriccion()
        context['data_fotos_solo_nacion'] = generador_datos_fotos.datos_solo_nacion()
        # data carga
        generador_datos_carga_parcial = GeneradorDatosCargaParcialConsolidado(
            self.restriccion_geografica, self.categoria)
        if self.base_carga_parcial == "solo_con_fotos":
            generador_datos_carga_parcial.set_query_base(MesaCategoria.objects.exclude(mesa__attachments=None))
        generador_datos_carga_total = GeneradorDatosCargaTotalConsolidado(
            self.restriccion_geografica, self.categoria)
        if self.base_carga_total == "solo_con_fotos":
            generador_datos_carga_total.set_query_base(MesaCategoria.objects.exclude(mesa__attachments=None))
        context['data_carga_parcial'] = generador_datos_carga_parcial.datos()
        context['data_carga_total'] = generador_datos_carga_total.datos()
        # data preidentificaciones
        context['data_preidentificaciones'] = GeneradorDatosPreidentificacionesConsolidado(
            self.restriccion_geografica).datos()
        # data relacionada con navegación
        context['base_carga_parcial'] = self.base_carga_parcial
        context['base_carga_total'] = self.base_carga_total
        context['donde_volver'] = self.donde_volver()
        return context

    def donde_volver(self):
        return f'acr-{self.base_carga_parcial}-{self.base_carga_total}'

    def calcular_restriccion(self):
        if self.restriccion_geografica_spec == "None":
            return SinRestriccion()
        else:
            spec_data=self.restriccion_geografica_spec.split('-')
            if spec_data[0] == 'Distrito':
                return RestriccionPorDistrito(spec_data[1])
            elif spec_data[0] == 'Seccion':
                return RestriccionPorSeccion(spec_data[1])
            else:
                raise Exception(f'especificación desconocida: {spec_data}')

    def data_categorias_posibles(self):
        data_categorias = []
        hay_demasiadas_categorias = False
        if self.restriccion_geografica.restringe_algo():
            if self.restriccion_geografica.query_categorias().count() > 20:
                hay_demasiadas_categorias = True
            else:
                for categoria in self.restriccion_geografica.query_categorias():
                    data_categorias.append({ 'id': categoria.id, 'nombre': categoria.nombre })
        return data_categorias, hay_demasiadas_categorias



def elegir_categoria_avance_carga_resumen(request, *args, **kwargs):
    categoria_elegida = request.POST.copy().get('categoria')
    print('en elegir_categoria_avance_carga_resumen, categoría elegida')
    print(categoria_elegida)
    print(kwargs.get('carga_parcial'))
    return redirect('avance-carga-resumen',
                    carga_parcial=kwargs.get('carga_parcial'),
                    carga_total=kwargs.get('carga_total'),
                    restriccion_geografica=kwargs.get('restriccion_geografica'),
                    categoria=categoria_elegida)


class EleccionDeDistritoOSeccion(TemplateView):
    template_name = "elecciones/eleccion_distrito_o_seccion.html"

    def dispatch(self, *args, **kwargs):
        self.hay_criterio_para_busqueda = self.kwargs.get('hay_criterio') == "True"
        self.valor_busqueda = self.kwargs.get('valor_criterio')
        self.donde_volver = self.kwargs.get('donde_volver')
        self.codigo_mensaje = self.kwargs.get('mensaje')
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # texto de búsqueda
        context['texto_busqueda'] = self.valor_busqueda
        # análisis del valor a buscar
        context['opciones'] = []
        if self.hay_criterio_para_busqueda:
            if len(self.valor_busqueda) < 3:
                self.codigo_mensaje = 'corto'
            else:
                busqueda = BusquedaDistritoOSeccion()
                busqueda.set_valor_busqueda(self.valor_busqueda)
                if busqueda.hay_demasiados_resultados():
                    self.codigo_mensaje = 'demasiados_resultados'
                elif len(busqueda.resultados()) == 0:
                    self.codigo_mensaje = 'sin_resultados'
                else:
                    context['opciones'] = busqueda.resultados()
        # consecuencias del análisis anterior
        context['cantidad_opciones'] = len(context['opciones'])
        context['mensaje'] = self.mensaje()
        # donde volver
        context['donde_volver'] = self.donde_volver
        # listo
        return context

    def mensaje(self):
        if (self.codigo_mensaje == 'corto'):
            return {'texto': 'Debe ingresar, al menos, tres caracteres', 'hay_que_mostrar': True}
        elif (self.codigo_mensaje == 'sin_resultados'):
            return {'texto': 'No hay ninguna división geográfica que corresponda a la búsqueda', 'hay_que_mostrar': True}
        elif (self.codigo_mensaje == 'demasiados_resultados'):
            return {'texto': 'Hay demasiados resultados, refinar la búsqueda', 'hay_que_mostrar': True}
        elif (self.codigo_mensaje == 'no_se_eligio_opcion'):
            return {'texto': 'No se eleigió ninguna opción; repetir la búsqueda', 'hay_que_mostrar': True}
        else:
            return {'texto': 'todo liso', 'hay_que_mostrar': False}


def ingresar_parametro_busqueda(request, *args, **kwargs):
    valor_ingresado = request.POST.copy().get('parametro_busqueda')
    donde_volver = kwargs.get('donde_volver')
    return redirect(
        'elegir-distrito-o-seccion', 
        hay_criterio='True', 
        valor_criterio=valor_ingresado, donde_volver=donde_volver, 
        mensaje='nada')


def eleccion_efectiva_distrito_o_seccion(request, *args, **kwargs):
    valor_elegido = request.POST.copy().get('distrito_o_seccion')
    if valor_elegido == None:
        return redirect(
            'elegir-distrito-o-seccion',
            hay_criterio='False',
            valor_criterio='', 
            donde_volver=kwargs.get('donde_volver'),
            mensaje='no_se_eligio_opcion')
    else:
        spec_donde_volver = kwargs.get('donde_volver').split('-')
        # el parámetro donde_volver es de la forma acr-<carga_parcial>-<carga_total>-<restriccion-geografica>
        donde_volver = {'carga_parcial': spec_donde_volver[1], 'carga_total': spec_donde_volver[2]}
        return redirect('avance-carga-resumen', 
            carga_parcial=donde_volver['carga_parcial'], 
            carga_total=donde_volver['carga_total'], 
            restriccion_geografica=valor_elegido,
            categoria='None')


def limpiar_busqueda(request, *args, **kwargs):
    spec_donde_volver = kwargs.get('donde_volver').split('-')
    # el parámetro donde_volver es de la forma acr-<carga_parcial>-<carga_total>-<restriccion-geografica>
    donde_volver = {'carga_parcial': spec_donde_volver[1], 'carga_total': spec_donde_volver[2]}
    return redirect('avance-carga-resumen',
                    carga_parcial=donde_volver['carga_parcial'],
                    carga_total=donde_volver['carga_total'],
                    restriccion_geografica="None",
                    categoria='None')
