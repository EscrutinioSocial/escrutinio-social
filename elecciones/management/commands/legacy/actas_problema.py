from django.conf import settings
from adjuntos.models import Attachment



class Command(BaseCommand):

    def handle(self, *args, **options):

        for a in Attachment.objects.filter(probema__isnull=False):
            print(f'*** {settings.ALLOWED_HOSTS} ***')
            print(a.id, a.problema)
            print('')