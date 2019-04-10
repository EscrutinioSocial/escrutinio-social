import re
from csv import DictReader
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from nameparser import HumanName
from elecciones.models import LugarVotacion, Mesa
from fiscales.models import Fiscal, AsignacionFiscalGeneral
from contacto.forms import DatoDeContactoModelForm





def apellido_nombres(nombre, apellido):
    raw = f'{nombre} {apellido}'.strip()
    nombre = HumanName(raw)
    apellido = nombre.last.title()
    nombres = nombre.first.title()
    if nombre.middle:
        nombres += f' {nombre.middle}'.title()
    return apellido, nombres




class Command(BaseCommand):
    help = "importar fiscales generales"


    def add_arguments(self, parser):
        parser.add_argument('csv')


    def success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def warning(self, msg):
        self.stdout.write(self.style.WARNING(msg))


    def add_telefono(self, objeto, telefono):
        ct = ContentType.objects.get(app_label='fiscales', model=type(objeto).__name__.lower())

        d = DatoDeContactoModelForm({
            'tipo': 'teléfono',
            'valor': telefono,
            'content_type': ct.id,
            'object_id': objeto.id
        })

        if d.is_valid():
            dato = d.save(commit=False)
            try:
                dato.full_clean(validate_unique=True)
                dato.save()
                self.success(f'Importado {dato} para {objeto}')
                return
            except ValidationError:
                error = 'Este dato ya existe'
        else:
            error = d.errors
        self.warning(f'Ignorado: {error}')

    def handle(self, *args, **options):
        path = options['csv']
        try:
            data = DictReader(open(path))
        except Exception as e:
            raise CommandError(f'Archivo no válido\n {e}')

        for row in data:
            if not row['Nombres'] or not row['mesa_desde']:
                continue

            if not row['DNI']:
                self.warning(f"{row['Nombres']} fiscal sin dni")
                continue

            dni = re.sub("[^0-9]", "", row['DNI'])
            apellido, nombres = apellido_nombres(row['Nombres'], row['Apellidos'])
            tipo = 'general' if row['mesa_hasta'] else 'de_mesa'

            fiscal, created = Fiscal.objects.get_or_create(dni=dni, defaults={
                'nombres': nombres,
                'apellido': apellido,
                'tipo': tipo
            })
            if created:
                self.success(f'creado {fiscal}')
            else:
                self.warning(f'{fiscal} existente (dni {fiscal.dni})')

            self.add_telefono(fiscal, row['Telefono'])




            if row['mesa_hasta']:
                try:
                    escuela = LugarVotacion.objects.filter(mesas__numero=row['mesa_desde']).get(mesas__numero=row['mesa_hasta'])
                except LugarVotacion.DoesNotExist:
                    self.warning(f"No se encontró escuela para row['mesa_desde'] - row['mesa_hasta']")
                    continue

                asignacion, created = AsignacionFiscalGeneral.objects.get_or_create(fiscal=fiscal, lugar_votacion=escuela)
                if created:
                    self.success(f'Asignacion: {asignacion}')
                else:
                    self.warning(f'{asignacion} ya existia')


            else:
                try:
                    mesa = Mesa.objects.get(numero=row['mesa_desde'])
                except Mesa.DoesNotExist:
                    self.warning(f"No se encontró mesa row['mesa_desde']")
                    continue

                asignacion, created = AsignacionDeMesa.objects.get_or_create(fiscal=fiscal, mesa=mesa)
                if created:
                    self.success(f'creado {asignacion}')
                else:
                    self.warning(f'{asignacion} ya existia')

