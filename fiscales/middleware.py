from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.sessions.models import Session
from django.contrib.auth import logout



class OneSessionPerUserMiddleware:
    LAST_SEEN_KEY = "last_seen"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            fiscal = request.user.fiscal
            # Me fijo si viene de la sesión válida.
            session_key = request.session.session_key
            if fiscal.session_key != session_key:
                logout(request)
                return render(request, 'fiscales/sesion-expirada.html')

        response = self.get_response(request)

        return response
