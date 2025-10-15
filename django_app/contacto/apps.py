from django.apps import AppConfig
from material.frontend.apps import ModuleMixin


class ContactoConfig(ModuleMixin, AppConfig):
    name = 'contacto'
    icon = '<i class="material-icons">settings_applications</i>'
