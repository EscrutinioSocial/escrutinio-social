from django.contrib import admin
from django_admin_row_actions import AdminRowActionsMixin

from .models import ColaCargasPendientes


class ColaCargasPendientesAdmin(AdminRowActionsMixin, admin.ModelAdmin):
    model = ColaCargasPendientes
    extra = 0
    ordering = ['orden']
    raw_id_fields = ('mesa_categoria', 'attachment', 'distrito', 'seccion')
    list_display = [
        'id', 'orden', 'mesa_categoria', 'get_status', 'attachment', 'distrito', 'seccion'
    ]

    def get_status(self, obj):
        return f'{obj.mesa_categoria.status}'
    get_status.short_description = "Status mesacat"


admin.site.register(ColaCargasPendientes, ColaCargasPendientesAdmin)
