from django.forms.fields import CharField
from django.core.exceptions import ValidationError
from django.conf import settings


def validar_status(value):
    valores = set(value.split())
    todos = {s[0] for s in settings.MC_STATUS_CHOICE}
    if valores != todos:
        raise ValidationError('Faltan o sobran status. Poné uno por línea.')


class StatusTextFields(CharField):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validators.append(validar_status)
