from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import get_text_list
from django.views.generic.base import TemplateView

from .definiciones import VisualizadoresOnlyMixin

from escrutinio_social import settings

from fiscales.models import Fiscal

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
from elecciones.busquedas import BusquedaDistritoOSeccion

from elecciones.resultados_resumen import (
    GeneradorDatosFotosConsolidado, GeneradorDatosPreidentificacionesConsolidado,
    GeneradorDatosCargaParcialConsolidado, GeneradorDatosCargaTotalConsolidado,
    GeneradorDatosFotosPorDistrito, GeneradorDatosFotosDistritoPorSeccion,
    GeneradorDatosCargaParcialDiscriminada,
    SinRestriccion, RestriccionPorDistrito, RestriccionPorSeccion
)

from django.contrib.auth.decorators import login_required, user_passes_test
from urllib.parse import urlsplit

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
        # context['distritos'] = Distrito.objects.all().order_by('nombre')
        context['mostrar_electores'] = not settings.OCULTAR_CANTIDADES_DE_ELECTORES
        return context

class AvanceDeCargaCategoriaCuerpoCentral(AvanceDeCargaCategoria):
    template_name = "elecciones/avance-carga-cuerpo-central.html"

@login_required
@user_passes_test(lambda u: u.fiscal.esta_en_grupo('visualizadores'), login_url='permission-denied')
def menu_lateral_avance_carga(request, categoria_id):

    # Si no viene categoría mandamos a PV.
    categoria = categoria_id
    if categoria_id is None:
        categoria = Categoria.objects.get(slug=settings.SLUG_CATEGORIA_PRESI_Y_VICE).id
        return redirect('avance-carga-nuevo-menu', categoria_id=categoria)

    context = {}
    context['distritos'] = Distrito.objects.all().extra(
        select={'numero_int': 'CAST(numero AS INTEGER)'}
    ).prefetch_related(
        'secciones_politicas',
        'secciones',
        'secciones__circuitos'
    ).order_by('numero_int')
    context['cat_id'] = categoria

    # Agrego al contexto el host del servidor para armar los links del menú
    url_parts = urlsplit(request.build_absolute_uri(None))
    context['host'] = url_parts.scheme + '://' + url_parts.netloc

    return render(request, 'elecciones/menu-lateral-avance-carga.html', context=context)

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
        self.string_data_extra = self.kwargs.get('data_extra')
        self.data_extra = parse_data_extra(self.string_data_extra)
        self.detalle_foto = self.data_extra['foto']
        self.detalle_carga_parcial_confirmada = self.data_extra['cargaparcialconfirmada']
        self.detalle_carga_parcial_csv = self.data_extra['cargaparcialcsv']
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
        # context['ancho_dato'] = 's1' if self.restriccion_geografica.restringe_algo() else 's2'
        # context['ancho_titulo'] = 's2' if self.restriccion_geografica.restringe_algo() else 's4'
        context['ancho_dato'] = 's1'
        context['ancho_titulo'] = 's2'
        # categorias
        context['categorias'], context['hay_demasiadas_categorias'] = self.data_categorias_posibles()
        context['categoria_elegida'] = self.categoria_spec
        context['nombre_categoria_elegida'] = self.categoria.nombre
        # data fiscales
        ahora = timezone.now()
        desde = ahora - timedelta(minutes=5)
        context['fiscales_activos'] = Fiscal.objects.filter(last_seen__gt=desde).count()
        # data fotos
        generador_datos_fotos = GeneradorDatosFotosConsolidado(self.restriccion_geografica)
        context['data_fotos_nacion_pba_restriccion'] = generador_datos_fotos.datos_nacion_pba_restriccion()
        context['data_fotos_solo_nacion'] = generador_datos_fotos.datos_solo_nacion()
        # data carga
        generador_datos_carga_parcial = GeneradorDatosCargaParcialConsolidado(
            self.restriccion_geografica, self.categoria)
        if self.base_carga_parcial == "solo_con_fotos":
            generador_datos_carga_parcial.set_query_base(
                MesaCategoria.objects.exclude(mesa__attachments=None))
        generador_datos_carga_total = GeneradorDatosCargaTotalConsolidado(
            self.restriccion_geografica, self.categoria)
        if self.base_carga_total == "solo_con_fotos":
            generador_datos_carga_total.set_query_base(MesaCategoria.objects.exclude(mesa__attachments=None))
        context['data_carga_parcial'] = generador_datos_carga_parcial.datos()
        context['data_carga_total'] = generador_datos_carga_total.datos()
        # data preidentificaciones
        context['data_preidentificaciones'] = GeneradorDatosPreidentificacionesConsolidado(
            self.restriccion_geografica).datos()
        # data extra
        context['detalle_foto'] = self.detalle_foto
        context['detalle_carga_parcial_confirmada'] = self.detalle_carga_parcial_confirmada
        context['detalle_carga_parcial_csv'] = self.detalle_carga_parcial_csv
        # detalle fotos
        if self.detalle_foto == 'distrito':
            context['datos_detalle_foto'] = GeneradorDatosFotosPorDistrito().datos()
        elif self.detalle_foto == 'seccion':
            context['datos_detalle_foto'] = GeneradorDatosFotosDistritoPorSeccion(
                settings.DISTRITO_PBA).datos()
        # detalle carga parcial confirmada
        if self.detalle_carga_parcial_confirmada == 'distrito':
            context['datos_detalle_carga_parcial_confirmada'] = GeneradorDatosCargaParcialDiscriminada(
                settings.SLUG_CATEGORIA_PRESI_Y_VICE, 'mesa__circuito__seccion__distrito__nombre').para_carga_confirmada().datos()
        elif self.detalle_carga_parcial_confirmada == 'seccion':
            context['datos_detalle_carga_parcial_confirmada'] = GeneradorDatosCargaParcialDiscriminada(
                settings.SLUG_CATEGORIA_GOB_Y_VICE_PBA, 'mesa__circuito__seccion__nombre').para_carga_confirmada().datos()
        # detalle carga parcial csv
        if self.detalle_carga_parcial_csv == 'distrito':
            context['datos_detalle_carga_parcial_csv'] = GeneradorDatosCargaParcialDiscriminada(
                settings.SLUG_CATEGORIA_PRESI_Y_VICE, 'mesa__circuito__seccion__distrito__nombre').para_carga_csv().datos()
        elif self.detalle_carga_parcial_csv == 'seccion':
            context['datos_detalle_carga_parcial_csv'] = GeneradorDatosCargaParcialDiscriminada(
                settings.SLUG_CATEGORIA_GOB_Y_VICE_PBA, 'mesa__circuito__seccion__nombre').para_carga_csv().datos()
        # data relacionada con navegación
        context['base_carga_parcial'] = self.base_carga_parcial
        context['base_carga_total'] = self.base_carga_total
        context['donde_volver'] = self.donde_volver()
        context['data_extra'] = self.string_data_extra
        return context

    def donde_volver(self):
        return f'acr-{self.base_carga_parcial}-{self.base_carga_total}'

    def calcular_restriccion(self):
        if self.restriccion_geografica_spec == "None":
            return SinRestriccion()
        else:
            spec_data = self.restriccion_geografica_spec.split('-')
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
            if self.restriccion_geografica.query_categorias().count() > 50:
                hay_demasiadas_categorias = True
            else:
                for categoria in self.restriccion_geografica.query_categorias():
                    data_categorias.append({'id': categoria.id, 'nombre': categoria.nombre})
        return data_categorias, hay_demasiadas_categorias


def elegir_categoria_avance_carga_resumen(request, *args, **kwargs):
    categoria_elegida = request.POST.copy().get('categoria')
    return redirect('avance-carga-resumen',
                    carga_parcial=kwargs.get('carga_parcial'),
                    carga_total=kwargs.get('carga_total'),
                    restriccion_geografica=kwargs.get('restriccion_geografica'),
                    categoria=categoria_elegida,
                    data_extra=kwargs.get('data_extra'))


def elegir_detalle_avance_carga_resumen(request, *args, **kwargs):
    detalle_elegido = kwargs.get('seleccion')
    data_detalle = detalle_elegido.split('_')
    tipo_detalle = data_detalle[0]
    valor_detalle = data_detalle[1]
    data_extra = parse_data_extra(kwargs.get('data_extra'))
    data_extra[tipo_detalle] = valor_detalle
    return redirect('avance-carga-resumen',
                    carga_parcial=kwargs.get('carga_parcial'),
                    carga_total=kwargs.get('carga_total'),
                    restriccion_geografica=kwargs.get('restriccion_geografica'),
                    categoria=kwargs.get('categoria'),
                    data_extra=format_data_extra(data_extra))


def parse_data_extra(string_data_extra):
    partes = string_data_extra.split('_')
    return { 'foto': partes[0], 'cargaparcialconfirmada': partes[1], 'cargaparcialcsv': partes[2] }

def format_data_extra(struct_data_extra):
    return struct_data_extra['foto'] + '_' + struct_data_extra['cargaparcialconfirmada'] + '_' + struct_data_extra['cargaparcialcsv']


class EleccionDeDistritoOSeccion(TemplateView):
    template_name = "elecciones/eleccion_distrito_o_seccion.html"

    def dispatch(self, *args, **kwargs):
        self.hay_criterio_para_busqueda = self.kwargs.get('hay_criterio') == "True"
        self.valor_busqueda = self.kwargs.get('valor_criterio') if self.hay_criterio_para_busqueda else ''
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
    hay_criterio = len(valor_ingresado) > 0
    donde_volver = kwargs.get('donde_volver')
    return redirect(
        'elegir-distrito-o-seccion',
        hay_criterio='True' if hay_criterio else 'False',
        valor_criterio=valor_ingresado if hay_criterio else 'None',
        donde_volver=donde_volver,
        mensaje='nada' if hay_criterio else 'corto')


def eleccion_efectiva_distrito_o_seccion(request, *args, **kwargs):
    valor_elegido = request.POST.copy().get('distrito_o_seccion')
    if valor_elegido == None:
        return redirect(
            'elegir-distrito-o-seccion',
            hay_criterio='False',
            valor_criterio='None',
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
                        categoria='None',
                        data_extra='nada_nada_nada')


def limpiar_busqueda(request, *args, **kwargs):
    spec_donde_volver = kwargs.get('donde_volver').split('-')
    # el parámetro donde_volver es de la forma acr-<carga_parcial>-<carga_total>-<restriccion-geografica>
    donde_volver = {'carga_parcial': spec_donde_volver[1], 'carga_total': spec_donde_volver[2]}
    return redirect('avance-carga-resumen',
                    carga_parcial=donde_volver['carga_parcial'],
                    carga_total=donde_volver['carga_total'],
                    restriccion_geografica="None",
                    categoria='None',
                    data_extra='nada_nada_nada')
