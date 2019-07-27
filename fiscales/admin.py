import csv
from django.db.models import Q
from django.urls import reverse
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from .models import Fiscal
from .forms import FiscalForm
from contacto.admin import ContactoAdminInline
from django_admin_row_actions import AdminRowActionsMixin
from django.contrib.admin.filters import DateFieldListFilter
from antitrolling.models import EventoScoringTroll
from functools import lru_cache
from django.utils.html import format_html

class FechaIsNull(DateFieldListFilter):
    def __init__(self, field, request, params, model, model_admin, field_path):
        super().__init__(field, request, params, model, model_admin, field_path)
        self.links = self.links[-2:]


class EsStaffFilter(admin.SimpleListFilter):
    title = 'Es Staff'
    parameter_name = 'es_staff'

    def lookups(self, request, model_admin):
        return (
            ('sí', 'sí'),
            ('no', 'no'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "sí":
            queryset = queryset.filter(user__is_staff=True)
        elif value == "no":
            queryset = queryset.filter(user__is_staff=False)
        return queryset


def hacer_staff(modeladmin, request, queryset):
    for f in queryset:
        f.user.is_staff = True
        f.user.save(update_fields=['is_staff'])
hacer_staff.short_description = "Hacer staff (dataentry)"

class EventoScoringTrollInline(admin.TabularInline):
    model = EventoScoringTroll
    extra = 0
    fk_name = "fiscal_afectado"
    readonly_fields = ('motivo', 'mesa_categoria', 'attachment_link', 'automatico', 'actor', 'variacion')
    exclude = ['attachment']
    verbose_name = "Evento que afecta al scoring troll del fiscal"
    verbose_name_plural = "Eventos que afectan al scoring troll del fiscal"
    can_delete = False

    # probablemente haya una mejor forma de hacer esto.
    def attachment_link(self,obj):
        img_snippet = f'<img src="{obj.attachment.foto.url}" width="80px"/>'
        return format_html(f'<a href="{obj.attachment.foto.url}">'+img_snippet+'</a>')

    def has_add_permission(self, request):
        return False


class FiscalAdmin(AdminRowActionsMixin, admin.ModelAdmin):
    actions = [hacer_staff]

    def get_row_actions(self, obj):
        row_actions = []
        if obj.user:
            row_actions.append(
                {
                    'label': f'Loguearse como {obj.nombres}',
                    'url': f'/hijack/{obj.user.id}/',
                    'enabled': True,
                }
            )
        if obj.estado == 'AUTOCONFIRMADO':
            row_actions.append(
                {
                    'label': f'Confirmar Fiscal',
                    'url': reverse('confirmar-fiscal', args=(obj.id,)),
                    'enabled': True,
                    'method': 'POST',
                }
            )
        label_troll = 'troll' if not obj.troll else 'no troll'
        row_actions.append(
            {
                'label': f'Marcar como {label_troll}',
                'url': reverse('cambiar-status-troll', args=(obj.id, not obj.troll)),
                'enabled': True
            }
        )


        row_actions += super().get_row_actions(obj)
        return row_actions

    def scoring_troll(o):
        return o.scoring_troll()

    def es_staff(o):
        return o.user.is_staff

    es_staff.boolean = True

    form = FiscalForm
    list_display = ('__str__', 'dni', es_staff, 'troll', scoring_troll)
    search_fields = ('apellido', 'nombres', 'dni',)
    list_display_links = ('__str__',)
    list_filter = (EsStaffFilter, 'estado', 'troll')
    inlines = [
        EventoScoringTrollInline,
        ContactoAdminInline,
    ]


admin.site.register(Fiscal, FiscalAdmin)
