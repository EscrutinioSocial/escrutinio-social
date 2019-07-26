from django.apps import AppConfig


#class EleccionesAppConfig(AppConfig):
#    name = 'elecciones'

class EleccionesAppConfig(AppConfig):
    name = 'elecciones'
    # This function is the only new thing in this file
    # it just imports the signal file when the app is ready
    def ready(self):
        import elecciones.signals

