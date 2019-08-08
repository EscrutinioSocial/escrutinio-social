from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings

class Command(BaseCommand):
    help = "Mail de prueba."

    def add_arguments(self, parser):
        parser.add_argument('--dest', type=str, help='Destinatario.')

    def handle(self, *args, **options):
        email = options['dest']
        send_mail(
            '[NOREPLY] Recibimos tu inscripción como validador/a.',
            "Prueba",
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
            html_message="Esto es una <b>prueba</b>."
        )