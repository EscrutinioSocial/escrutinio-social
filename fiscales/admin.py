import csv
from django.db.models import Q
from django.urls import reverse
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from .models import Fiscal, AsignacionFiscalGeneral, AsignacionFiscalDeMesa, Organizacion
from .forms import FiscalForm
from contacto.admin import ContactoAdminInline
from django_admin_row_actions import AdminRowActionsMixin
from django.contrib.admin.filters import DateFieldListFilter


ARCHIVO_EMAILS_FISCALES = 'emails_fiscales.csv'


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


class AsignadoFilter(admin.SimpleListFilter):
    title = 'Asignación'
    parameter_name = 'asignado'

    def lookups(self, request, model_admin):
        return (
            ('sí', 'sí'),
            ('no', 'no'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            isnull = value == 'no'
            general = Q(
                tipo='general',
                asignacion_escuela__isnull=isnull,
                asignacion_escuela__eleccion__slug='generales2017'
            )
            de_mesa = Q(
                tipo='de_mesa',
                asignacion_mesa__isnull=isnull,
                asignacion_mesa__mesa__eleccion__slug='generales2017'
            )
            queryset = queryset.filter(general | de_mesa)
        return queryset


class ReferenteFilter(admin.SimpleListFilter):
    title = 'Referente'
    parameter_name = 'referente'

    def lookups(self, request, model_admin):
        return (
            ('sí', 'sí'),
            ('no', 'no'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            isnull = value == 'no'
            queryset = queryset.filter(es_referente_de_circuito__isnull=isnull).distinct()
        return queryset


def exportar_email_fiscales(modeladmin, request, queryset):
    emails_fiscales = []
    for fiscal in queryset.all():
        for contacto in fiscal.datos_de_contacto.all():
            if contacto.tipo == 'email':
                emails_fiscales.append(contacto.valor)

    with open(ARCHIVO_EMAILS_FISCALES, 'w') as csvfile:
        spamwriter = csv.writer(csvfile)
        spamwriter.writerow(emails_fiscales)

    return queryset

exportar_email_fiscales.short_description = "Exportar Email Fiscales"

def hacer_staff(modeladmin, request, queryset):
    for f in queryset:
        f.user.is_staff = True
        f.user.save(update_fields=['is_staff'])

hacer_staff.short_description = "Hacer staff (dataentry)"


class FiscalAdmin(AdminRowActionsMixin, admin.ModelAdmin):
    actions = [exportar_email_fiscales, hacer_staff]
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

        label_asignacion = 'Editar asignación a' if  obj.asignacion else 'Asignar a'
        if obj.es_general and obj.asignacion:
            url = reverse('admin:fiscales_asignacionfiscalgeneral_change', args=(obj.asignacion.id,))
        elif obj.es_general and not obj.asignacion:
            url = reverse('admin:fiscales_asignacionfiscalgeneral_add') + f'?fiscal={obj.id}'
        elif obj.asignacion:
            url = reverse('admin:fiscales_asignacionfiscaldemesa_change', args=(obj.asignacion.id,))
        else:
            url = reverse('admin:fiscales_asignacionfiscaldemesa_add') + f'?fiscal={obj.id}'

        row_actions.append({
            'label': f'{label_asignacion} escuela' if obj.es_general else f'{label_asignacion} mesa',
            'url': url,
            'enabled': True
        })

        escuelas_ids = ','.join(str(id) for id in obj.escuelas.values_list('id', flat=True))
        row_actions.append({
                'label': 'Escuelas asignadas',
                'url': reverse('admin:elecciones_lugarvotacion_changelist') + f'?id__in={escuelas_ids}',
                'enabled': True
        })

        row_actions += super().get_row_actions(obj)
        return row_actions

    def telefonos(o):
        return ' / '.join(o.telefonos)

    def asignado_a(o):
        if o.asignacion:
            return o.asignacion.lugar_votacion if o.es_general else o.asignacion.mesa

    def es_staff(o):
        return o.user.is_staff
    es_staff.boolean = True

    form = FiscalForm
    list_display = ('__str__', 'dni', 'tipo', es_staff, telefonos)
    search_fields = (
        'apellido', 'nombres', 'direccion', 'dni',
        'asignacion_escuela__lugar_votacion__nombre',
        'asignacion_mesa__mesa__lugar_votacion__nombre'
    )
    list_display_links = ('__str__',)
    raw_id_fields = ("escuela_donde_vota",)
    list_filter = (EsStaffFilter, 'estado', 'email_confirmado', AsignadoFilter, 'tipo', ReferenteFilter, 'organizacion')
    readonly_fields = ('mesas_desde_hasta',)
    inlines = [
        ContactoAdminInline,
    ]


def asignar_comida(modeladmin, request, queryset):
    queryset.update(comida='asignada')


class AsignacionFiscalAdmin(AdminRowActionsMixin, admin.ModelAdmin):
    list_filter = (('ingreso', FechaIsNull), ('egreso', FechaIsNull), 'comida')
    actions = [asignar_comida]

    def get_row_actions(self, obj):
        row_actions = []
        if obj.fiscal:
            row_actions.append(
                {
                    'label': 'Ver fiscal',
                    'url': reverse('admin:fiscales_fiscal_changelist') + f'?id={obj.fiscal.id}',
                    'enabled': True,
                }
            )
        row_actions += super().get_row_actions(obj)
        return row_actions


class AsignacionFiscalGeneralAdmin(AsignacionFiscalAdmin):

    list_filter = ('eleccion', 'lugar_votacion__circuito',) + AsignacionFiscalAdmin.list_filter

    list_display = ('fiscal', 'lugar_votacion', 'ingreso', 'egreso', 'comida')
    search_fields = (
        'fiscal__apellido', 'fiscal__nombres', 'fiscal__direccion', 'fiscal__dni',
        'lugar_votacion__nombre',
        'lugar_votacion__direccion',
        'lugar_votacion__barrio',
        'lugar_votacion__ciudad',
    )
    raw_id_fields = ("lugar_votacion", "fiscal")


class AsignacionFiscalDeMesaAdmin(AsignacionFiscalAdmin):

    list_filter = ('mesa__eleccion', 'mesa__lugar_votacion__circuito',) + AsignacionFiscalAdmin.list_filter

    list_display = ('fiscal', 'mesa', 'ingreso', 'egreso', 'comida')
    raw_id_fields = ("mesa", "fiscal")
    search_fields = (
        'fiscal__apellido', 'fiscal__nombres', 'fiscal__direccion', 'fiscal__dni',
        'mesa__numero',
        'mesa__lugar_votacion__nombre',
        'mesa__lugar_votacion__direccion',
        'mesa__lugar_votacion__barrio',
        'mesa__lugar_votacion__ciudad',
    )



admin.site.register(AsignacionFiscalGeneral, AsignacionFiscalGeneralAdmin)
admin.site.register(AsignacionFiscalDeMesa, AsignacionFiscalDeMesaAdmin)
admin.site.register(Fiscal, FiscalAdmin)
admin.site.register(Organizacion)
