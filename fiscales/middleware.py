from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import render
from fiscales.models import Fiscal


class OneSessionPerUserMiddleware:
    LAST_SEEN_KEY = "last_seen"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                fiscal = request.user.fiscal
                # Me fijo si viene de la sesión válida.
                session_key = request.session.session_key
                if fiscal.session_key != session_key:
                    logout(request)
                    return render(request, 'fiscales/sesion-expirada.html')

                # Me fijo si hay que actualizarle el last_seen
                last_seen = request.session.get(self.LAST_SEEN_KEY)
                ahora = timezone.now()
                delta = timedelta(seconds=settings.LAST_SEEN_UPDATE_INTERVAL)

                if not last_seen or ahora > last_seen + delta:
                    # Me actualizo el last_seen en la bd.
                    fiscal.update_last_seen(ahora)
            except Fiscal.DoesNotExist:
                # usuario no fiscal
                pass
        response = self.get_response(request)
        return response
