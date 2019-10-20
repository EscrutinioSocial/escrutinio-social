from django.contrib import admin
from django.shortcuts import reverse
from django.utils.html import format_html
from djangoql.admin import DjangoQLSearchMixin
from .models import Problema, ReporteDeProblema
from django import forms
from django_admin_row_actions import AdminRowActionsMixin


def marcar_resuelto(modeladmin, request, queryset):
    queryset.update(estado=Problema.ESTADOS.resuelto)


marcar_resuelto.short_description = "Marcar como resueltos"


class ProblemaForm(forms.ModelForm):

    class Meta:
        model = Problema
        exclude = []


class ReporteDeProblemaInline(admin.StackedInline):
    model = ReporteDeProblema
    raw_id_fields = ('identificacion', 'carga', 'reportado_por', )
    extra = 0


class ProblemaAdmin(DjangoQLSearchMixin, AdminRowActionsMixin, admin.ModelAdmin):

    def mesa_(o):
        if o.mesa:
            return format_html(f'<a href="/admin/elecciones/mesa/?id={o.mesa.id}">{o.mesa}</a>')
    mesa_.allow_tags = True
    mesa_.short_description = "Nro de mesa"

    def attachment_(o):
        if o.attachment:
            img_snippet = f'<img src="{o.attachment.foto.url}" width="80px"/>'
            return format_html(f'<a href="/admin/adjuntos/attachment/?id={o.attachment.id}">{img_snippet}</a>')
    attachment_.allow_tags = True
    attachment_.short_description = "Attachment"

    def descripciones(o):
        reportes = "<br>".join([str(reporte) for reporte in o.reportes.all()])
        return reportes

    def get_row_actions(self, obj):
        row_actions = []
        row_actions.append({
            'label': 'Aceptar',
            'url': reverse('cambiar-estado-problema', args=[obj.id, Problema.ESTADOS.en_curso]),
            'enabled': True
        })
        row_actions.append({
            'label': 'Resolver',
            'url': reverse('cambiar-estado-problema', args=[obj.id, Problema.ESTADOS.resuelto]),
            'enabled': True
        })
        row_actions.append({
            'label': 'Descartar',
            'url': reverse('cambiar-estado-problema', args=[obj.id, Problema.ESTADOS.descartado]),
            'enabled': True
        })

        row_actions += super().get_row_actions(obj)
        return row_actions

    list_display = ('id', mesa_, attachment_, 'estado', descripciones, 'resuelto_por')
    raw_id_fields = ('attachment', 'mesa', 'resuelto_por', )
    list_filter = ('estado',)
    search_fields = (
        'mesa__numero',
    )
    inlines = [ReporteDeProblemaInline]
    ordering = ['id']


admin.site.register(Problema, ProblemaAdmin)
