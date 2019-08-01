from django.core.management.base import BaseCommand, CommandError
from fiscales.models import Fiscal
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.contrib.auth.models import Group

class Command(BaseCommand):
    help = """ Generar accesos para los usuarios del sistema
            Ejemplos:
                ./manage.py generar_accesos_data_entries  # 20 usuarios para cada partido
                ./manage.py generar_accesos_data_entries --equipo=ALL --cantidad=1 # un usuario para cada partido
                ./manage.py generar_accesos_data_entries  --cantidad=10 # 10 usuarios para un equipo nuevo
            """

    def add_arguments(self, parser):
        parser.add_argument('--prefijo', default='usr', type=str, help='Prefijo de los usuarios al que se agrega _ y el nro de serie.')
        parser.add_argument('--cantidad', default=20, type=int, help='Cantidad de usuarios a crear.')
        parser.add_argument('--grupo', default='fiscales con acceso al bot', type=str, help='En qué grupo se agregan.')


    def crear_acceso(self, prefijo, indice, grupo, sobre_escribir=True):
        username = slugify(f'{prefijo}_{indice:02d}')

        user, created = User.objects.get_or_create(username=username)
        user.is_staff= True
        if created or sobre_escribir:
            password = User.objects.make_random_password().lower()[0:8]
            user.set_password(password)
        else:
            password = None

        user.save()

        fiscal, created = Fiscal.objects.get_or_create(user=user)
        fiscal.estado = 'CONFIRMADO'
        fiscal.notas = f'Generado automáticamente en el grupo {grupo.name} por el sistema'
        fiscal.email_confirmado = True
        fiscal.apellido = username
        fiscal.nombres = username
        fiscal.save()

        # Lo agrego al grupo.
        user.groups.add(grupo)

        return user, password

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Generando usuarios ---'))

        prefijo = options['prefijo']
        cantidad = options['cantidad']
        nombre_grupo = options['grupo']
        grupo = Group.objects.get(name=nombre_grupo)

        for i in range(cantidad):
            user, clave = self.crear_acceso(prefijo=prefijo, indice=i, grupo=grupo, sobre_escribir=True)
            self.stdout.write(self.style.SUCCESS(f'Usuario {user}, clave "{clave}" (sin las comillas).'))


        self.stdout.write(self.style.SUCCESS('--- Terminado. ---'))


