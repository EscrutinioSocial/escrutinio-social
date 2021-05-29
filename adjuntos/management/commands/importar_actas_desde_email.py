import time
import easyimap

from constance import config
from django.conf import settings
from django.db import IntegrityError

from adjuntos.models import Email, Attachment
from django.core.files.base import ContentFile
from elecciones.management.commands.basic_command import BaseCommand


class Command(BaseCommand):
    help = "Importa actas de archivos adjuntos en las cuentas de emails (ver settings.IMAP)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-seen', action='store_true', help='Incluye email ya leídos')
        parser.add_argument(
            '--only-images', action='store_true', help="Sólo considerar adjuntos que sean de tipo imágen")
        parser.add_argument(
            '--deamon', action='store_true', help="Ejecutar como demonio")

    def handle(self, *args, **options):
        super().handle(*args, **options)
        if options['deamon']:
            finalizar = False
            while not finalizar:
                try:
                    self.check_emails(**options)
                    time.sleep(config.PAUSA_IMPORTAR_EMAILS)
                except KeyboardInterrupt:
                    finalizar = True
        else:
            self.check_emails(**options)

    def check_emails(self, **options):
        imaps = settings.IMAPS
        for imap in imaps:

            imapper = easyimap.connect(imap['host'], imap['user'], imap['pass'], imap['mailbox'])
            self.success('Loggueado como {}'.format(imap['user']))
            if options['include_seen']:
                # read every email not present in the db
                imap_ids = {int(i) for i in imapper.listids()}
                known_ids = set(Email.objects.values_list('uid', flat=True))
                unknown_ids = imap_ids - known_ids
                mails = (imapper.mail(str(i)) for i in unknown_ids)
            else:
                mails = imapper.unseen()

            for mail in mails:
                self.success(f'From: {mail.from_addr} | Asunto: {mail.title} ')
                attachments = mail.attachments
                if not attachments:
                    self.warning(' ... sin adjuntos')
                    continue

                email = Email.from_mail_object(mail)
                for attachment in attachments:
                    # self.success(' -- attachment {}'.format(attachment[0]))
                    if options['only_images'] and not attachment[2].startswith('image'):
                        self.warning(f'Ignoring {attachment[0]} ({attachment[2]})')
                        continue
                    instance = Attachment(
                        email=email,
                        mimetype=attachment[2]
                    )

                    try:
                        content = ContentFile(attachment[1])
                        instance.foto.save(attachment[0], content, save=False)
                        instance.save()
                        self.success(f'{instance} -- importado')
                    except IntegrityError:
                        self.warning(f'{attachment[0]} ya está en el sistema')
