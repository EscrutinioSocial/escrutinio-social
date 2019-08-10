from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from html2text import html2text


def enviar_correo(titulo, fiscal, email):
    body_html = render_to_string(
        'fiscales/email.html', {
            'fiscal': fiscal,
            'email': settings.DEFAULT_FROM_EMAIL,
            'cell_call': settings.DEFAULT_CEL_CALL,
            'cell_local': settings.DEFAULT_CEL_LOCAL,
            'site_url': settings.FULL_SITE_URL
        }
    )
    body_text = html2text(body_html)

    send_mail(
        titulo,
        body_text,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
        html_message=body_html
    )
