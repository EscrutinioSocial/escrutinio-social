from django.contrib import admin
from django.shortcuts import reverse
from .models import Attachment
from django_admin_row_actions import AdminRowActionsMixin


class AttachmentAdmin(AdminRowActionsMixin, admin.ModelAdmin):
    list_display = ('status', 'mesa', 'foto', 'foto_edited', 'taken')
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


admin.site.register(Attachment, AttachmentAdmin)
