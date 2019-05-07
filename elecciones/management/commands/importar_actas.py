import easyimap
from django.conf import settings

from adjuntos.models import Email, Attachment
from django.core.files.base import ContentFile
from elecciones.management.commands.importar_carta_marina_2019_gobernador import escrutinio_socialBaseCommand



class Command(escrutinio_socialBaseCommand):
    help = "Importa adjunto del email {}".format(settings.IMAP_ACCOUNT)

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-seen', action='store_true')
        parser.add_argument(
            '--only-images', action='store_true')

    def handle(self, *args, **options):

        for imap in settings.IMAPs:
        
            imapper = easyimap.connect(imap['host'], imap['user'], imap['pass'], imap['mailbox'])
            self.success('Loggueado')
            if options['include_seen']:
                # read every email not present in the db
                imap_ids = {int(i) for i in imapper.listids()}
                known_ids = set(Email.objects.values_list('uid', flat=True))
                unknown_ids = imap_ids - known_ids
                mails = (imapper.mail(str(i)) for i in unknown_ids)
            else:
                mails = imapper.unseen()

            for mail in mails:
                attachments = mail.attachments
                if not attachments:
                    continue

                email = Email.from_mail_object(mail)
                self.log(email)
                for attachment in attachments:
                    if options['only_images'] and not attachment[2].startswith('image'):
                        self.warning(f'Ignoring {attachment[0]} ({attachment[2]})')
                        continue
                    instance = Attachment(
                        email=email,
                        mimetype=attachment[2]
                    )
                    content = ContentFile(attachment[1])
                    instance.foto.save(attachment[0], content, save=False)
                    instance.save()
                    self.log(instance)