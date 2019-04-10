from django.contrib import admin
from django.shortcuts import reverse
from .models import Problema
# Register your models here.
from django_admin_row_actions import AdminRowActionsMixin


class ProblemaAdmin(AdminRowActionsMixin, admin.ModelAdmin):

    def mesa_(o):
        return f'<a href="/admin/elecciones/mesa/?numero={o.mesa.numero}"">{o.mesa}</a>'
    mesa_.allow_tags = True

    list_display = ('problema', mesa_, 'descripcion', 'reportado_por', 'estado')
    list_filter = ('problema', 'estado')
    search_fields = (
        'mesa__numero',
    )

    def get_row_actions(self, obj):
        row_actions = []
        row_actions.append({
            'label': 'Editar/Cargar Mesa',
            'url': reverse('mesa-cargar-resultados', args=[1, obj.mesa.numero]),
            'enabled': True
        })
        row_actions += super().get_row_actions(obj)
        return row_actions

admin.site.register(Problema, ProblemaAdmin)