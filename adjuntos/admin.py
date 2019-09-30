from django.contrib import admin
from django.shortcuts import reverse
from .models import Attachment, Identificacion, CSVTareaDeImportacion
from django_admin_row_actions import AdminRowActionsMixin


class CSVTareaDeImportacionAdmin(AdminRowActionsMixin, admin.ModelAdmin):
    list_display = ('id', 'csv_file', 'fiscal', 'status', 'mesas_total_ok', 'mesas_parc_ok', 'created', 'modified')
    list_filter = ('status',)
    search_fields = ('csv_file', 'fiscal__user__username')


class IdentificacionInline(admin.StackedInline):
    model = Identificacion
    extra = 0
    raw_id_fields = ('fiscal', 'mesa')


class AttachmentAdmin(AdminRowActionsMixin, admin.ModelAdmin):
    list_display = ('status', 'mesa', 'foto', 'foto_edited', 'cant_fiscales_asignados', 'subido_por', 'pre_identificacion')
    list_filter = ('status',)
    search_fields = ('mesa__numero', 'subido_por__user__username')
    raw_id_fields = ('email', 'mesa', 'subido_por', 'pre_identificacion', 'identificacion_testigo')

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