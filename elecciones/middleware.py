#Session model stores the session data
from django.contrib.sessions.models import Session

class OneSessionPerUserMiddleware:
    # Called only once when the web server starts
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        if request.user.is_authenticated:
            u = request.user
            stored_session_key = request.user.logged_in_user.session_key

            # If there is a stored_session_key in our database and it is
            # different from the current session, delete the stored_session_key
            # session_key with from the Session table.
            if stored_session_key and stored_session_key != request.session.session_key:
                Session.objects.get(session_key=stored_session_key).delete()

            request.user.logged_in_user.session_key = request.session.session_key
            request.user.logged_in_user.save()

        response = self.get_response(request)

        return response

