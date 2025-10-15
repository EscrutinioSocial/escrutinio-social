from csv import DictReader
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from fiscales.models import Fiscal
from datetime import datetime
from annoying.functions import get_object_or_None
from contacto.forms import DatoDeContactoModelForm
from localflavor.ar.forms import ARDNIField
from django import forms


class DniForm(forms.Form):
    dni = ARDNIField(required=False)

class EmailForm(forms.Form):
    email = forms.EmailField()


class Command(BaseCommand):
    help = "Importar fiscales voluntarios"

    def success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def warning(self, msg):
        self.stdout.write(self.style.WARNING(msg))

    def add_arguments(self, parser):
        parser.add_argument('csv')

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
                self.success(f'   Importado {dato} para {objeto}')
                return
            except ValidationError:
                error = '   Este dato ya existe'
        else:
            error = d.errors
        self.warning(f'   Ignorado: {error}')

    def handle(self, *args, **options):
        path = options['csv']
        now = datetime.now()
        try:
            data = DictReader(open(path))
        except Exception as e:
            raise CommandError(f'Archivo no válido\n {e}')

        for row in data:
            email_f = EmailForm({'email': row['Dirección de correo electrónico']})
            email = email_f.cleaned_data['email'] if email_f.is_valid() else None
            if not email:
                self.warning(f"Ignorando {row['Apellido']}, {row['Nombre']}: sin email")
                continue

            try:
                fiscal = get_object_or_None(Fiscal,
                                        datos_de_contacto__valor=email,
                                        datos_de_contacto__tipo='email')
            except Fiscal.MultipleObjectsReturned:
                self.warning(f"Ignorando {row['Apellido']}, {row['Nombre']}: más de un fiscal con este email")
                continue
            if fiscal:
                self.warning(f"Ignorando {row['Apellido']}, {row['Nombre']}: email conocido")
                continue
            dni = None
            dni_raw = row.get('DNI')
            if dni_raw:
                dni_f = DniForm({'dni': dni_raw})
                dni =  dni_f.cleaned_data['dni'] if dni_f.is_valid() else None
            if dni and get_object_or_None(Fiscal, dni=dni):
                self.warning(f"Ignorando {row['Apellido']}, {row['Nombre']}: dni conocido")
                continue

            fiscal, _ = Fiscal.objects.get_or_create(
                dni=dni,
                nombres=row['Nombre'].strip().title(),
                apellido=row['Apellido'].strip().title(),
                defaults=dict(
                    movilidad=row['¿Posee movilidad?'] == 'Sí' if row.get('¿Posee movilidad?') else None,
                    disponibilidad=row['Disponibilidad '].lower(),

                    direccion=row['Lugar de residencia (Barrio, localidad, departamento)'],
                    tipo='de_mesa',
                    estado='IMPORTADO',
                    notas=f'Importado {now}'
                )
            )
            fiscal.agregar_dato_de_contacto('email', email)
            self.add_telefono(fiscal, row['Teléfono'])
            self.success(f'Importado {fiscal}')



