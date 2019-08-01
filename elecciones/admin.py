from django.contrib import admin
from django.urls import reverse
from djangoql.admin import DjangoQLSearchMixin
from leaflet.admin import LeafletGeoAdmin
from .models import (
    Distrito,
    SeccionPolitica,
    Seccion,
    Circuito,
    LugarVotacion,
    Mesa,
    Partido,
    Carga,
    Opcion,
    CategoriaOpcion,
    Categoria,
    VotoMesaReportado,
    MesaCategoria,
    Eleccion,
    TecnicaProyeccion,
    AgrupacionCircuitos,
    AgrupacionCircuito,
)
from django.http import HttpResponseRedirect
from django_admin_row_actions import AdminRowActionsMixin


class HasLatLongListFilter(admin.SimpleListFilter):
    """
    Filtro para escuelas
    """
    title = 'Tiene coordenadas'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'coordenadas'

    def lookups(self, request, model_admin):
        return (
            ('sí', 'sí'),
            ('no', 'no'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            isnull = value == 'no'
            queryset = queryset.filter(geom__isnull=isnull)
        return queryset


class TieneResultados(admin.SimpleListFilter):
    """
    filtro para mesas
    """
    title = 'Tiene resultados'
    parameter_name = 'tiene_resultados'

    def lookups(self, request, model_admin):
        return (
            ('sí', 'sí'),
            ('no', 'no'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value is not None:
            isnull = value == 'no'
            queryset = Mesa.objects.filter(cargas__isnull=isnull)
        return queryset


def mostrar_en_mapa(modeladmin, request, queryset):
    selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
    ids = ",".join(selected)
    mapa_url = reverse('mapa')
    return HttpResponseRedirect(f'{mapa_url}?ids={ids}')


mostrar_en_mapa.short_description = "Mostrar seleccionadas en el mapa"


def mostrar_resultados_escuelas(modeladmin, request, queryset):
    selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
    ids = ",".join(selected)
    mapa_url = reverse('resultados_escuelas')
    return HttpResponseRedirect(f'{mapa_url}?ids={ids}')


mostrar_resultados_escuelas.short_description = "Mostrar resultados de Escuelas seleccionadas"


def resultados_reportados(modeladmin, request, queryset):

    selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
    name = modeladmin.model.__name__.lower()
    ids = "&".join(f'{name}={s}' for s in selected)
    res_url = reverse('resultados-categoria', args=[1])
    return HttpResponseRedirect(f'{res_url}?{ids}')


resultados_reportados.short_description = "Ver Resultados"


class LugarVotacionAdmin(AdminRowActionsMixin, LeafletGeoAdmin):

    def sección(o):
        return o.circuito.seccion.numero

    list_display = (
        'nombre', 'direccion', 'ciudad', 'circuito', sección, 'mesas_desde_hasta', 'electores',
        'estado_geolocalizacion'
    )
    list_display_links = ('nombre', )
    list_filter = (HasLatLongListFilter, 'circuito__seccion', 'circuito')
    search_fields = ('nombre', 'direccion', 'ciudad', 'barrio', 'mesas__numero')
    show_full_result_count = False
    actions = [mostrar_en_mapa, resultados_reportados]

    def get_row_actions(self, obj):
        row_actions = [{
            'label': 'Mesas',
            'url': reverse('admin:elecciones_mesa_changelist') + f'?lugar_votacion__id={obj.id}',
            'enabled': True,
        }]
        row_actions += super().get_row_actions(obj)
        return row_actions


def mostrar_resultados_mesas(modeladmin, request, queryset):
    selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
    ids = ",".join(selected)
    mapa_url = reverse('resultados_mesas_ids')
    return HttpResponseRedirect(f'{mapa_url}?ids={ids}')


mostrar_resultados_mesas.short_description = "Mostrar resultados de Mesas seleccionadas"


class MesaAdmin(AdminRowActionsMixin, admin.ModelAdmin):
    actions = [resultados_reportados]
    list_display = ('numero', 'lugar_votacion')
    list_filter = (
        TieneResultados, 'es_testigo', 'lugar_votacion__circuito__seccion', 'lugar_votacion__circuito'
    )
    search_fields = (
        'numero',
        'lugar_votacion__nombre',
        'lugar_votacion__direccion',
        'lugar_votacion__ciudad',
        'lugar_votacion__barrio',
    )

    def get_row_actions(self, obj):
        row_actions = []
        for e in obj.categorias.all():
            row_actions.append({
                'label': f'Ver resultados {e}',
                'url': reverse('resultados-categoria', args=(e.id, )) + f'?mesa={obj.id}',
                'enabled': True
            })

        row_actions.append({
            'label': 'Escuela',
            'url': reverse('admin:elecciones_lugarvotacion_changelist') + f'?id={obj.lugar_votacion.id}',
            'enabled': True,
        })
        row_actions += super().get_row_actions(obj)
        return row_actions


class PartidoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'nombre')
    list_display_links = list_display


class MesaCategoriaAdmin(admin.ModelAdmin):
    list_display = ('mesa', 'categoria', 'status')
    list_filter = ['status', 'categoria', 'mesa__circuito', 'mesa__circuito__seccion']


class CircuitoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'seccion')
    list_display_links = list_display
    list_filter = ('seccion', )
    search_fields = (
        'nombre',
        'numero',
    )


class DistritoAdmin(admin.ModelAdmin):
    search_fields = (
        'nombre',
        'numero',
    )


class SeccionPoliticaAdmin(admin.ModelAdmin):
    list_display = ['numero', 'nombre', 'distrito']

    search_fields = (
        'nombre',
        'numero',
    )


class SeccionAdmin(admin.ModelAdmin):
    list_display = ['numero', 'nombre', 'distrito', 'seccion_politica']

    search_fields = (
        'nombre',
        'numero',
    )


class VotoMesaReportadoAdmin(DjangoQLSearchMixin, admin.ModelAdmin):
    list_display = [
        'carga',
        'id',
        'opcion',
        'opcion_orden',
        'votos',
    ]
    list_display_links = list_display
    list_filter = ('carga__mesa_categoria__categoria', 'opcion')
    search_fields = [
        'carga__mesa_categoria__mesa__numero',
        'carga__mesa_categoria__mesa__circuito__nombre',
        'carga__mesa_categoria__mesa__lugar_votacion__nombre'
    ]

    def opcion_orden(self, obj):
        return obj.opcion.orden


class OpcionAdmin(admin.ModelAdmin):
    list_display = ['id', 'nombre_corto', 'partido', 'nombre', 'orden']


class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'activa', 'color', 'back_color']
    search_fields = ['nombre']
    list_filter = ['activa']


class CategoriaOpcionAdmin(admin.ModelAdmin):
    search_fields = ['categoria__nombre', 'opcion__nombre']
    ordering = ['categoria__nombre', 'opcion__orden']


class TecnicaProyeccionAdmin(admin.ModelAdmin):
    search_fields = ['nombre']
    ordering = ['nombre']


class AgrupacionCircuitoInline(admin.TabularInline):
    model = AgrupacionCircuito
    extra = 3


class AgrupacionCircuitosAdmin(admin.ModelAdmin):
    search_fields = ['proyeccion', 'nombre']
    ordering = ['proyeccion']
    list_filter = ('proyeccion', )
    inlines = (AgrupacionCircuitoInline, )


admin.site.register(Eleccion)
admin.site.register(Carga)
admin.site.register(Distrito, DistritoAdmin)
admin.site.register(SeccionPolitica, SeccionPoliticaAdmin)
admin.site.register(Seccion, SeccionAdmin)
admin.site.register(Circuito, CircuitoAdmin)
admin.site.register(Partido, PartidoAdmin)
admin.site.register(LugarVotacion, LugarVotacionAdmin)
admin.site.register(Mesa, MesaAdmin)
admin.site.register(MesaCategoria, MesaCategoriaAdmin)
admin.site.register(VotoMesaReportado, VotoMesaReportadoAdmin)
admin.site.register(Opcion, OpcionAdmin)
admin.site.register(Categoria, CategoriaAdmin)
admin.site.register(CategoriaOpcion, CategoriaOpcionAdmin)
admin.site.register(TecnicaProyeccion, TecnicaProyeccionAdmin)
admin.site.register(AgrupacionCircuitos, AgrupacionCircuitosAdmin)
