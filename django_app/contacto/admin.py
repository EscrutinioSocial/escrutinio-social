from django.contrib import admin
from .models import DatoDeContacto
from .forms import DatoDeContactoModelForm
from django.contrib.contenttypes.admin import GenericTabularInline


class ContactoAdminInline(GenericTabularInline):
    model = DatoDeContacto
    form = DatoDeContactoModelForm


admin.site.register(DatoDeContacto)
