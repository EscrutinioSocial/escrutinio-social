import datetime
from django.utils import timezone
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from fiscales.email_sender import enviar_correo


class Command(BaseCommand):

    help = "Envía correos de 'volvé a participar'."

    def add_arguments(self, parser):
        parser.add_argument('--dia', default=15, type=int, help='Día hasta cuándo')
        parser.add_argument('--mes', default=10, type=int, help='Mes hasta cuándo')
        parser.add_argument('--hora', default=12, type=int, help='Hora hasta cuándo')
        parser.add_argument('--anio', default=2019, type=int, help='Año hasta cuándo')

    def handle(self, *args, **options):
        dia = options['dia']
        mes = options['mes']
        hora = options['hora']
        anio = options['anio']

        fecha_hasta = datetime.datetime(year=anio, month=mes, day=dia, hour=hora, tzinfo=timezone.utc)
        users = User.objects.filter(
            date_joined__lte=fecha_hasta
        ).exclude(
            username__icontains='test'
        ).exclude(
            email__icontains='nodomain'
        ).filter(
            last_name='Schapachnik'
        )

        self.stdout.write(self.style.SUCCESS(
            f"Se enviarán {len(users)} correos de registración a los usuarios registrados "
            f"antes de la fecha {fecha_hasta}."
        ))

        confirmado = self.boolean_input("Desea seguir (s/n)?", default="n")
        if not confirmado:
            return

        for user in users:
            fiscal = user.fiscal
            emails = list(fiscal.emails)
            # si el mail que está en el user no está en los datos de contacto, lo agregamos por las dudas
            if user.email not in emails:
                emails.append(user.email)

            for email in emails:
                enviar_correo(
                    '[NOREPLY] Contamos con vos para cuidar los votos del domingo.',
                    fiscal,
                    email,
                    template='fiscales/email_volve_a_participar.html'
                )

    def boolean_input(self, question, default=None):
        result = input(self.style.SUCCESS("%s ") % question)
        if not result and default is not None:
            return default
        while len(result) < 1 or result[0].lower() not in "sn":
            result = input(self.style.WARNING("Responda s o n: "))
        return result[0].lower() == "s"
