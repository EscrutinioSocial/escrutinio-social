from django.contrib import admin
from django.shortcuts import reverse
from .models import Problema
# Register your models here.
from django_admin_row_actions import AdminRowActionsMixin


def marcar_resuelto(modeladmin, request, queryset):
    queryset.update(estado=Problema.ESTADOS.resuelto)


marcar_resuelto.short_description = "Marcar como resueltos"



class ProblemaAdmin(AdminRowActionsMixin, admin.ModelAdmin):

    def mesa_(o):
        return f'<a href="/admin/elecciones/mesa/?numero={o.mesa.numero}"">{o.mesa}</a>'
    mesa_.allow_tags = True

    list_display = (mesa_, 'estado')
    list_filter = ('estado',)
    search_fields = (
        'mesa__numero',
    )

    def get_row_actions(self, obj):
        row_actions = []

        for e in obj.mesa.categoria.all():
            row_actions.append({
                'label': f'Editar/Cargar {e}',
                'url': reverse('mesa-cargar-resultados', args=[e.id, obj.mesa.numero]),
                'enabled': True
            })
        row_actions += super().get_row_actions(obj)
        return row_actions

admin.site.register(Problema, ProblemaAdmin)