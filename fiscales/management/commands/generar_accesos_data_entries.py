from django.core.management.base import BaseCommand, CommandError
from fiscales.models import Fiscal
from django.contrib.auth.models import User
from django.utils.text import slugify
from elecciones.models import Partido


class Command(BaseCommand):
    help = """ Generar accesos para los data entries del día de la eleccion
            Ejemplos:
                ./manage.py generar_accesos_data_entries --equipo=ALL # 20 usuarios para cada partido
                ./manage.py generar_accesos_data_entries --equipo=ALL --cantidad=1 # un usuario para cada partido 
                ./manage.py generar_accesos_data_entries --equipo=BUNKER_BECARIOS --cantidad=10 # 10 usuarios para un equipo nuevo  
            """

    def add_arguments(self, parser):
        parser.add_argument('--equipo', default='general', type=str, help='Nombre de quipo (ej: FIT, UCR, Humanista, etc. ALL para hacerle claves a todos los partidos')
        parser.add_argument('--cantidad', default=20, type=int, help='Cantidad de usuarios fiscalizadores a crear')


    def crear_acceso(self, nombre, c, sobre_escribir=True):
        username = slugify(f'{nombre} {c}')
        
        user, created = User.objects.get_or_create(username=username)
        user.is_staff= True
        if created or sobre_escribir:
            password = User.objects.make_random_password()
            user.set_password(password)
        else:
            password = None

        user.save()

        fiscal, created = Fiscal.objects.get_or_create(user=user)
        fiscal.estado = 'CONFIRMADO'
        fiscal.notas = f'Generado automaticamente en el equipo {nombre} por el sistema'
        fiscal.email_confirmado = True
        fiscal.apellido = nombre
        fiscal.nombres = nombre
        fiscal.save()

        return user, password

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- generando usuarios ---'))

        equipo = options['equipo']
        cantidad = options['cantidad']

        if equipo == 'ALL':
            equipos = []
            partidos = Partido.objects.all()
            for partido in partidos:
                equipos.append(partido.nombre_corto)
        else:
            equipos = [equipo]
        
        for equipo in equipos:
            self.stdout.write(self.style.SUCCESS('--- Creando usuarios fiscales de {} ---'.format(equipo)))
            for c in range(cantidad):
                user, clave = self.crear_acceso(nombre=equipo, c=c, sobre_escribir=True)
                self.stdout.write(self.style.SUCCESS('Usuario {}, clave {}'.format(user, clave)))


        self.stdout.write(self.style.SUCCESS('--- terminado ---'))
    
    
