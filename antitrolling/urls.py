from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^cambiar_status_troll/(?P<fiscal_id>\d+)/(?P<prender>[\w-]+)$',
        views.cambiar_status_troll, name='cambiar-status-troll'),
]
