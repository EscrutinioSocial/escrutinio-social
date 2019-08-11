from django.core.management.base import BaseCommand, CommandError
from csv import DictReader
from django.core.mail import send_mail

from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "importar fiscales generales"

    def add_arguments(self, parser):
        parser.add_argument('csv')

    def success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def warning(self, msg):
        self.stdout.write(self.style.WARNING(msg))

    def handle(self, *args, **options):
        path = options['csv']
        
        try:
            data = DictReader(open(path, encoding='utf-8'))
        except Exception as e:
            raise CommandError(f'Archivo no válido\n {e}')
        
        mails_enviados = 0
        for fiscal_data in data:
            # mando mail
            nombre = fiscal_data["Nombre"]
            referente = "Javier Rodríguez"
            subject = "Todos los votos - registrate para ser validador"
            from_address = "validar@frentedetodos.org"
            text_message_lines = \
                [
                    f'Estimado/a compañero/a {nombre}, ',
                    '',
                    'Sabemos que te propusiste colaborar como validador/a en "Todos los Votos",',
                    'el sistema informático para hacer nuestro propio recuento de control.',
                    '',
                    'Te pedimos que te inscribas en el formulario que aparecerá en ',
                    '      https://validar.frentedetodos.org/quiero-validar/06KM',
                    'para poder registrar todos tus datos y habilitarte para que ingreses hoy a "Todos los Votos".',
                    'Como "nombre de referente" indicá a Javier Rodríguez.',
                    '',
                    'Cómo funciona el sistema: ',
                    '',
                    '1) A partir de las 18.30 hs de todo el país nos van a llegar las fotos de las actas directamente de nuestros fiscales',
                    '2) Vamos a recibir esa información en un Centro de Cómputos virtual ',
                    '3) Se la vamos a pasar a un conjunto de validadoras y validadores, que se ocuparán de verificar los números desde su casa con la compu ',
                    '',
                    'Todo lo que vas a tener que hacer es mirar una imagen del Acta y al lado cargar los datos que te vayamos pidiendo, ¡es súper fácil!',
                    "",
                    "Para mayores detalles podés ver el video tutorial en https://www.youtube.com/embed/n1osvzuFx7I.",
                    "",
                    "Saludos cordiales",
                    "",
                    "Equipo de todoslosvotos"
                ]
            html_message_lines = \
                [
                    f'Estimado/a compañero/a {nombre}, ',
                    '',
                    'Sabemos que te propusiste colaborar como validador/a en <b>"Todos los Votos"</b>,',
                    'el sistema informático para hacer nuestro propio recuento de control.',
                    '',
                    'Te pedimos que te inscribas en el formulario que aparecerá en ',
                    '      <a href="https://validar.frentedetodos.org/quiero-validar/06KM">este link</a>',
                    'para poder registrar todos tus datos y habilitarte para que ingreses hoy a "Todos los Votos".',
                    'Como "nombre de referente" indicá a Javier Rodríguez.',
                    '',
                    'Cómo funciona el sistema: ',
                    '',
                    '1) A partir de las 18.30 hs de todo el país nos van a llegar las fotos de las actas directamente de nuestros fiscales',
                    '2) Vamos a recibir esa información en un Centro de Cómputos virtual ',
                    '3) Se la vamos a pasar a un conjunto de validadoras y validadores, que se ocuparán de verificar los números desde su casa con la compu ',
                    '',
                    'Todo lo que vas a tener que hacer es mirar una imagen del Acta y al lado cargar los datos que te vayamos pidiendo, ¡es súper fácil!',
                    "",
                    "Para mayores detalles podés ver el video tutorial en https://www.youtube.com/embed/n1osvzuFx7I.",
                    "",
                    "Saludos cordiales",
                    "",
                    "Equipo de todoslosvotos"
                ]
            self.success(f'mandando mail a {nombre}, dirección {fiscal_data["Email"]}')
            send_mail(
                subject,
                "\n".join(text_message_lines),
                from_address,
                [fiscal_data["Email"]],
                fail_silently=False,
                html_message="\n".join(html_message_lines)
            )
            mails_enviados += 1
        

        self.success(f"Listo, se enviaron {mails_enviados} mails")
        
