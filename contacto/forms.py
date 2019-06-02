import re
from django import forms
from django.conf import settings
from django.core.validators import validate_email, URLValidator
from django.contrib.contenttypes.forms import generic_inlineformset_factory
from .models import DatoDeContacto
import phonenumbers


CARACTERISTICA_TELEFONO_DEFAULT = settings.CARACTERISTICA_TELEFONO_DEFAULT

USERNAME_PATTERNS = {
    'twitter': re.compile(r'^((?:https?://(www\.)?twitter\.com/)|@)?(?P<username>\w{1,15})/?$'),
    'instagram': re.compile(r'^((?:https?://(www\.)?instagram\.com/)|@)?(?P<username>\w{3,20})/?$'),
    'facebook': re.compile(r'^(?:https?://(www\.)?facebook\.com/)?/?(?P<username>[\w\.]{3,50})/?(\?.*)?$'),
    'youtube': re.compile(r'^(?:https?://(www\.)?youtube\.com/(user/)?)?(?P<username>\w{3,40})/?$')
}


def validar_telefono(valor):
    CARACTERISTICA_DEFAULT = '351'
    valor = valor.strip()
    if valor.startswith(('15', '4')):
        valor = f'{CARACTERISTICA_DEFAULT} {valor}'
    elif valor.startswith('35') and 9 <= len(valor) <= 11:
        valor = f'9 {valor}'
    valor = phonenumbers.parse(valor, 'AR')
    formato = phonenumbers.PhoneNumberFormat.INTERNATIONAL
    valor = phonenumbers.format_number(valor, formato)
    return valor


class DatoDeContactoModelForm(forms.ModelForm):
    class Meta:
        model = DatoDeContacto
        exclude = []

    def clean_email(self, valor):
        try:
            validate_email(valor)
        except forms.ValidationError:
            self.add_error('valor', 'No es un email válido')

    def clean_telefono(self, valor):
        try:
            valor = validar_telefono(valor)
        except (AttributeError, phonenumbers.NumberParseException):
            self.add_error('valor', 'No es un teléfono válido')

        return valor

    def clean_username(self, tipo, valor):
        try:
            return re.match(USERNAME_PATTERNS[tipo], valor).group('username')
        except AttributeError:
            self.add_error('valor', f'No es un nombre de usuario de {tipo} válido')

    def clean_url(self, valor):
        validator = URLValidator()
        try:
            validator(valor)
        except ValidationError:
            self.add_error('valor', 'No es una dirección web válida')

    def clean(self):
        tipo = self.cleaned_data.get("tipo")
        valor = self.cleaned_data.get("valor", '').strip()

        if tipo == 'email':
            self.clean_email(valor)
        elif tipo == 'teléfono':
            valor = self.clean_telefono(valor)
        elif tipo in USERNAME_PATTERNS:
            valor = self.clean_username(tipo, valor)
        elif tipo == 'web':
            self.clean_url(valor)

        self.cleaned_data['valor'] = valor


ContactoInlineFormset = generic_inlineformset_factory(DatoDeContacto, form=DatoDeContactoModelForm, can_delete=True)

MinimoContactoInlineFormset = generic_inlineformset_factory(DatoDeContacto,
    form=DatoDeContactoModelForm,
    extra=2, can_delete=False
)