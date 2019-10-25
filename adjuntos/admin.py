from django.contrib import admin
from django.shortcuts import reverse
from .models import Attachment, Identificacion, CSVTareaDeImportacion
from django_admin_row_actions import AdminRowActionsMixin
from django_exportable_admin.admin import ExportableAdmin
from djangoql.admin import DjangoQLSearchMixin


class CSVTareaDeImportacionAdmin(AdminRowActionsMixin, admin.ModelAdmin):
    list_display = ('id', 'csv_file', 'fiscal', 'status', 'mesas_total_ok', 'mesas_parc_ok', 'created', 'modified')
    list_filter = ('status',)
    search_fields = ('csv_file', 'fiscal__user__username')
    raw_id_fields = ['fiscal']


class IdentificacionInline(admin.StackedInline):
    model = Identificacion
    extra = 0
    raw_id_fields = ('fiscal', 'mesa')


class AttachmentAdmin(DjangoQLSearchMixin, AdminRowActionsMixin, ExportableAdmin):
    list_display = ('status', 'mesa', 'foto', 'foto_edited', 'cant_fiscales_asignados', 'subido_por', 'get_distrito', 'get_seccion', 'pre_identificacion')
    list_filter = ('status',)
    search_fields = ('mesa__numero', 'subido_por__user__username', 'pre_identificacion__distrito__nombre', 'pre_identificacion__seccion__nombre',)
    raw_id_fields = ('email', 'mesa', 'subido_por', 'pre_identificacion', 'identificacion_testigo')

    def get_distrito(self, obj):
        if not obj.pre_identificacion:
            return '-'
        return obj.pre_identificacion.distrito
    get_distrito.admin_order_field = 'pre_identificacion__distrito'
    get_distrito.short_description = 'Distrito'

    def get_seccion(self, obj):
        if not obj.pre_identificacion:
            return '-'
        return obj.pre_identificacion.seccion
    get_seccion.admin_order_field = 'pre_identificacion__seccion'
    get_seccion.short_description = 'Sección'

    def get_row_actions(self, obj):
        row_actions = []
        row_actions.append({
            'label': 'AsignarMesa',
            'url': reverse('asignar-mesa', args=[obj.id]),
            'enabled': True
        })

        row_actions += super().get_row_actions(obj)
        return row_actions
    inlines = [IdentificacionInline]


admin.site.register(Attachment, AttachmentAdmin)
admin.site.register(CSVTareaDeImportacion, CSVTareaDeImportacionAdmin)