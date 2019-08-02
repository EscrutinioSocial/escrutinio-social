from django.apps import AppConfig


class EleccionesAppConfig(AppConfig):
    name = 'elecciones'

    def ready(self):
        import elecciones.system_checks

