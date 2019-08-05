from django.apps import AppConfig


class FiscalesAppConfig(AppConfig):
    name = 'fiscales'

    # Esta función se utiliza para importar las señales.
    def ready(self):
        import fiscales.signals

