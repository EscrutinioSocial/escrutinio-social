from django.contrib import admin
from django_admin_row_actions import AdminRowActionsMixin

from .models import ColaCargasPendientes


class ColaCargasPendientesAdmin(AdminRowActionsMixin, admin.ModelAdmin):
    model = ColaCargasPendientes
    extra = 0
    ordering = ['orden']
    raw_id_fields = ('mesa_categoria', 'attachment', 'distrito', 'seccion')
    list_display = ('id', 'orden', 'mesa_categoria', 'attachment', 'distrito', 'seccion')


admin.site.register(ColaCargasPendientes, ColaCargasPendientesAdmin)
