from django.contrib.auth import user_logged_in, user_logged_out
from django.dispatch import receiver
from fiscales.models import Fiscal


@receiver(user_logged_in)
def on_user_logged_in(sender, request, **kwargs):
    user = kwargs.get('user')
    try:
        fiscal = user.fiscal
        # Me guardo la session key.
        fiscal.update_session_key(request.session.session_key)
    except (AttributeError, Fiscal.DoesNotExist):
        # user sin fiscal
        pass


@receiver(user_logged_out)
def on_user_logged_out(sender, **kwargs):
    user = kwargs.get('user')
    try:
        fiscal = user.fiscal
        # Deslogueado.
        fiscal.update_session_key(None)
    except (AttributeError, Fiscal.DoesNotExist):
        # no estaba logueado o no tiene fiscal asociado
        pass