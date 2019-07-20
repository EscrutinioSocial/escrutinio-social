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

    list_display = ('problema', mesa_, 'descripcion', 'reportado_por', 'estado')
    list_filter = ('problema', 'estado')
    search_fields = (
        'mesa__numero',
    )

admin.site.register(Problema, ProblemaAdmin)