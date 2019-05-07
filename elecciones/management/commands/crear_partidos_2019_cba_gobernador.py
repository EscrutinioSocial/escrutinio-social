import easyimap
from django.conf import settings

from adjuntos.models import Email, Attachment
from django.core.files.base import ContentFile
from elecciones.management.commands.importar_carta_marina import BaseCommand
from elecciones.models import Partido


class Command(BaseCommand):
    help = "Importa adjunto del email {}".format(settings.IMAP_ACCOUNT)

    def handle(self, *args, **options):

        self.success('Creando partidos')

        """
        Hacemos por Córdoba: Juan Schiaretti
        Unión Cívica Radical: Ramón Mestre
        Córdoba Cambia: Mario Negri
        Frente de Izquierda y de los Trabajadores: Liliana Olivero
        Movimiento Socialistas de los Trabajadores: Luciana Echevarría
        Encuentro Vecinal Córdoba: Aurelio García Elorrio
        Avancemos Córdoba en Valores: Alberto Beltrán
        Movimiento al Socialismo: Eduardo Mulhall
        Partido PAIS: Enrique Sella
        Ucedé: Fernando Schüle
        Movimiento Acción Vecinal: Kasem Dandach
        Unión Ciudadana: Agustín Spaccesi
        """
        partido, created = Partido.objects.get_or_create(orden=100, numero=100, nombre='Hacemos por Córdoba - Schiaretti', nombre_corto='UPC')
        partido, created = Partido.objects.get_or_create(orden=100, numero=100, nombre='UCR - Mestre', nombre_corto='UCR')
        partido, created = Partido.objects.get_or_create(orden=100, numero=100, nombre='Córdoba Cambia - Negri', nombre_corto='Córdoba Cambia')
        partido, created = Partido.objects.get_or_create(orden=100, numero=100, nombre='FIT - Olivero', nombre_corto='FIT')
        partido, created = Partido.objects.get_or_create(orden=100, numero=100, nombre='MST - Echevarría', nombre_corto='MST')
        partido, created = Partido.objects.get_or_create(orden=100, numero=100, nombre='Encuentro Vecinal - Elorrio', nombre_corto='Encuentro Vecinal')
        partido, created = Partido.objects.get_or_create(orden=100, numero=100, nombre='Avancemos Córdoba - Beltrán', nombre_corto='Avancemos Córdoba')
        partido, created = Partido.objects.get_or_create(orden=100, numero=100, nombre='MAS - Mulhall', nombre_corto='MAS')
        partido, created = Partido.objects.get_or_create(orden=100, numero=100, nombre='PAIS - Sella', nombre_corto='PAIS')
        partido, created = Partido.objects.get_or_create(orden=100, numero=100, nombre='UCD - Schüle', nombre_corto='UCD')
        partido, created = Partido.objects.get_or_create(orden=100, numero=100, nombre='Movimiento Acción Vecinal - Dandach', nombre_corto='Mov Acción Vecinal')
        partido, created = Partido.objects.get_or_create(orden=100, numero=100, nombre='Unión Ciudadana - Spaccesi', nombre_corto='Unión Ciudadana')
