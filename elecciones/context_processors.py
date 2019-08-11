from django.conf import settings


def version(request):

    return {
        'timestamp_version': settings.APP_VERSION_NUMBER
    }
