from django.contrib import admin
from django.shortcuts import reverse
from .models import Attachment, Identificacion
from django_admin_row_actions import AdminRowActionsMixin


class IdentificacionInline(admin.StackedInline):
    model = Identificacion
    extra = 0

class AttachmentAdmin(AdminRowActionsMixin, admin.ModelAdmin):
    list_display = ('status', 'mesa', 'foto', 'foto_edited', 'taken', 'identificacion_parcial')
    list_filter = ('status',)
    search_fields = ('mesa__numero',)

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
