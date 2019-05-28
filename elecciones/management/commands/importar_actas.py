import easyimap
from django.conf import settings
from django.db import IntegrityError

from adjuntos.models import Email, Attachment
from django.core.files.base import ContentFile
from elecciones.management.commands.importar_carta_marina_2019_gobernador import BaseCommand


class Command(BaseCommand):
    help = "Importa adjunto de los emails configurados"

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-seen', action='store_true')
        parser.add_argument(
            '--only-images', action='store_true')

    def handle(self, *args, **options):


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

            # self.success('Se encontraron {} emails'.format(len(list(mails))))
            for mail in mails:
                self.success('Email {}'.format(mail))
                attachments = mail.attachments
                if not attachments:
                    self.success(' ... sin adjuntos')
                    continue
                
                email = Email.from_mail_object(mail)
                self.log(email)
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
                        self.success(' -- saved {}'.format(instance))
                        self.log(instance)
                    except IntegrityError:
                        self.warning(f'{attachment[0]} ya está en el sistema')
